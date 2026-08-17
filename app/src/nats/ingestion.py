"""NATS Bronze Ingestion Module for Databricks Community Edition

Provides real-time data ingestion from NATS broker with:
- Background thread execution (non-blocking)
- In-memory buffering with periodic micro-batch writes
- Delta Lake integration
- Graceful shutdown and status monitoring

Usage:
    ingestion = NATSBronzeIngestion(
        catalog="main",
        schema="albion",
        table="market_orders_bronze",
        buffer_size=1000,
        flush_interval_seconds=30
    )
    ingestion.start()
    # ... do other work ...
    status = ingestion.get_status()
    ingestion.stop()
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import nats
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    ArrayType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics for ingestion monitoring."""
    messages_received: int = 0
    messages_written: int = 0
    total_flushes: int = 0
    last_flush_time: Optional[float] = None
    errors: int = 0
    started_at: Optional[float] = None
    is_running: bool = False
    buffer_size: int = 0


class NATSBronzeIngestion:
    """Real-time NATS to Delta Lake Bronze ingestion.
    
    Subscribes to NATS topic, buffers messages in-memory, and periodically
    writes micro-batches to Delta Lake table. Runs in background thread.
    """

    # NATS connection details
    NATS_SERVER = "nats://public:thenewalbiondata@nats.albion-online-data.com:4222"
    NATS_SUBJECT = "marketorders.deduped"
    
    # Tick conversion constant (Windows ticks to Unix timestamp)
    WINDOWS_EPOCH_OFFSET = 621355968000000000
    TICKS_PER_SECOND = 10000000

    def __init__(
        self,
        catalog: str,
        schema: str,
        table: str,
        buffer_size: int = 1000,
        flush_interval_seconds: int = 30,
        max_retries: int = 3,
    ):
        """Initialize NATS Bronze Ingestion.
        
        Args:
            catalog: Unity Catalog catalog name
            schema: Schema name
            table: Target Bronze table name
            buffer_size: Max messages in buffer before auto-flush
            flush_interval_seconds: Time between periodic flushes
            max_retries: Max connection retry attempts
        """
        self.catalog = catalog
        self.schema = schema
        self.table = table
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval_seconds
        self.max_retries = max_retries
        
        # Full table name
        self.full_table_name = f"{catalog}.{schema}.{table}"
        
        # Thread-safe buffer
        self._buffer = deque(maxlen=buffer_size * 2)  # Extra capacity
        self._buffer_lock = threading.Lock()
        
        # Statistics
        self.stats = IngestionStats()
        self._stats_lock = threading.Lock()
        
        # Threading control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Spark session
        self.spark = SparkSession.builder.getOrCreate()
        
        # Ensure table exists
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create Bronze table if it doesn't exist."""
        schema = StructType([
            StructField("ingestion_timestamp", TimestampType(), False),
            StructField("message_id", LongType(), False),
            StructField("item_id", StringType(), True),
            StructField("item_name", StringType(), True),
            StructField("quality_level", IntegerType(), True),
            StructField("enchantment_level", IntegerType(), True),
            StructField("unit_price_silver", LongType(), True),
            StructField("amount", IntegerType(), True),
            StructField("auction_type", StringType(), True),
            StructField("expires_at", TimestampType(), True),
            StructField("location_id", IntegerType(), True),
            StructField("raw_json", StringType(), True),
        ])
        
        try:
            # Check if table exists
            table_exists = self.spark.catalog.tableExists(self.full_table_name)
            
            if not table_exists:
                logger.info(f"Creating Bronze table: {self.full_table_name}")
                
                # Create empty DataFrame with schema
                df = self.spark.createDataFrame([], schema)
                
                # Write as Delta table
                df.write \
                    .format("delta") \
                    .mode("overwrite") \
                    .saveAsTable(self.full_table_name)
                
                logger.info(f"Bronze table created successfully")
            else:
                logger.info(f"Bronze table already exists: {self.full_table_name}")
                
        except Exception as e:
            logger.error(f"Error ensuring table exists: {e}")
            raise

    def _convert_ticks_to_timestamp(self, ticks: int) -> datetime:
        """Convert Windows ticks to Python datetime.
        
        Args:
            ticks: Windows file time (100-nanosecond intervals since 1601-01-01)
            
        Returns:
            datetime object in UTC
        """
        unix_timestamp = (ticks - self.WINDOWS_EPOCH_OFFSET) / self.TICKS_PER_SECOND
        return datetime.utcfromtimestamp(unix_timestamp)

    def _parse_message(self, msg_data: bytes) -> Optional[Dict]:
        """Parse NATS message and extract fields.
        
        Args:
            msg_data: Raw message bytes from NATS
            
        Returns:
            Parsed message dict or None if parsing fails
        """
        try:
            raw = msg_data.decode('utf-8')
            data = json.loads(raw)
            
            # Extract and convert timestamp
            expires_ticks = data.get('Expires')
            expires_dt = None
            if expires_ticks:
                try:
                    expires_dt = self._convert_ticks_to_timestamp(expires_ticks)
                except Exception as e:
                    logger.warning(f"Failed to convert expires timestamp: {e}")
            
            # Build structured record
            record = {
                'ingestion_timestamp': datetime.utcnow(),
                'message_id': data.get('Id', 0),
                'item_id': data.get('ItemTypeId'),
                'item_name': data.get('ItemGroupTypeId'),  # Group name
                'quality_level': data.get('QualityLevel', 0),
                'enchantment_level': data.get('EnchantmentLevel', 0),
                'unit_price_silver': data.get('UnitPriceSilver', 0),
                'amount': data.get('Amount', 0),
                'auction_type': data.get('AuctionType'),
                'expires_at': expires_dt,
                'location_id': data.get('LocationId'),
                'raw_json': raw,  # Keep original for debugging
            }
            
            return record
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            with self._stats_lock:
                self.stats.errors += 1
            return None

    async def _message_handler(self, msg):
        """Async callback for NATS messages.
        
        Args:
            msg: NATS message object
        """
        parsed = self._parse_message(msg.data)
        
        if parsed:
            with self._buffer_lock:
                self._buffer.append(parsed)
            
            with self._stats_lock:
                self.stats.messages_received += 1
                self.stats.buffer_size = len(self._buffer)
            
            # Auto-flush if buffer is full
            if len(self._buffer) >= self.buffer_size:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Write buffered messages to Delta Lake."""
        # Get messages from buffer
        with self._buffer_lock:
            if not self._buffer:
                return
            
            messages = list(self._buffer)
            self._buffer.clear()
        
        try:
            # Create DataFrame from messages
            df = self.spark.createDataFrame(messages)
            
            # Append to Delta table
            df.write \
                .format("delta") \
                .mode("append") \
                .saveAsTable(self.full_table_name)
            
            # Update stats
            with self._stats_lock:
                self.stats.messages_written += len(messages)
                self.stats.total_flushes += 1
                self.stats.last_flush_time = time.time()
                self.stats.buffer_size = 0
            
            logger.info(f"Flushed {len(messages)} messages to {self.full_table_name}")
            
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
            with self._stats_lock:
                self.stats.errors += 1
            # Re-add messages to buffer for retry
            with self._buffer_lock:
                self._buffer.extendleft(reversed(messages))

    async def _periodic_flush(self):
        """Periodic flush task."""
        while not self._stop_event.is_set():
            await asyncio.sleep(self.flush_interval)
            if not self._stop_event.is_set():
                await self._flush_buffer()

    async def _run_async(self):
        """Main async event loop for NATS subscription."""
        retry_count = 0
        
        while retry_count < self.max_retries and not self._stop_event.is_set():
            try:
                # Connect to NATS
                logger.info(f"Connecting to NATS: {self.NATS_SERVER}")
                nc = await nats.connect(self.NATS_SERVER)
                logger.info("Connected to NATS successfully")
                
                # Subscribe to subject
                logger.info(f"Subscribing to: {self.NATS_SUBJECT}")
                sub = await nc.subscribe(self.NATS_SUBJECT, cb=self._message_handler)
                logger.info(f"Subscribed successfully")
                
                # Start periodic flush task
                flush_task = asyncio.create_task(self._periodic_flush())
                
                # Wait until stop event is set
                while not self._stop_event.is_set():
                    await asyncio.sleep(1)
                
                # Cleanup
                logger.info("Stopping ingestion...")
                flush_task.cancel()
                await self._flush_buffer()  # Final flush
                await nc.drain()
                await nc.close()
                logger.info("NATS connection closed")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"NATS error (attempt {retry_count}/{self.max_retries}): {e}")
                with self._stats_lock:
                    self.stats.errors += 1
                
                if retry_count < self.max_retries:
                    await asyncio.sleep(5 * retry_count)  # Exponential backoff
                else:
                    logger.error("Max retries reached. Stopping ingestion.")

    def _thread_runner(self):
        """Thread entry point that runs the async event loop."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Run async main
            self._loop.run_until_complete(self._run_async())
            
        except Exception as e:
            logger.error(f"Thread error: {e}")
        finally:
            if self._loop:
                self._loop.close()
            with self._stats_lock:
                self.stats.is_running = False

    def start(self):
        """Start background ingestion thread.
        
        Returns:
            True if started successfully, False if already running
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Ingestion already running")
            return False
        
        logger.info("Starting NATS Bronze ingestion...")
        
        # Reset state
        self._stop_event.clear()
        with self._stats_lock:
            self.stats = IngestionStats()
            self.stats.is_running = True
            self.stats.started_at = time.time()
        
        # Start background thread
        self._thread = threading.Thread(target=self._thread_runner, daemon=True)
        self._thread.start()
        
        logger.info("Ingestion thread started")
        return True

    def stop(self, timeout: int = 30):
        """Stop background ingestion gracefully.
        
        Args:
            timeout: Max seconds to wait for thread to finish
            
        Returns:
            True if stopped successfully, False on timeout
        """
        if not self._thread or not self._thread.is_alive():
            logger.warning("Ingestion not running")
            return True
        
        logger.info("Stopping ingestion...")
        self._stop_event.set()
        
        # Wait for thread to finish
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            logger.error(f"Thread did not stop within {timeout}s")
            return False
        
        logger.info("Ingestion stopped successfully")
        return True

    def get_status(self) -> Dict:
        """Get current ingestion status and statistics.
        
        Returns:
            Dictionary with status information
        """
        with self._stats_lock:
            uptime = None
            if self.stats.started_at:
                uptime = time.time() - self.stats.started_at
            
            last_flush_ago = None
            if self.stats.last_flush_time:
                last_flush_ago = time.time() - self.stats.last_flush_time
            
            return {
                'is_running': self.stats.is_running and (self._thread and self._thread.is_alive()),
                'uptime_seconds': uptime,
                'messages_received': self.stats.messages_received,
                'messages_written': self.stats.messages_written,
                'buffer_size': len(self._buffer),
                'total_flushes': self.stats.total_flushes,
                'last_flush_seconds_ago': last_flush_ago,
                'errors': self.stats.errors,
                'table': self.full_table_name,
            }

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, '_thread') and self._thread and self._thread.is_alive():
            logger.warning("Ingestion still running during cleanup, stopping...")
            self.stop(timeout=10)
