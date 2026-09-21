"""
Servidor MCP (Model Context Protocol) para Albion Online.

Expõe ferramentas agênticas para consulta de mercado em tempo real (NATS Firehose),
cotações consolidadas da REST API da AODP (com rate limiting e batching),
simulador econômico oficial e integração opcional com o Databricks Unity Catalog.
"""

import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

# Garante que a raiz do repositório esteja no sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.albion_mcp.core.metadata import metadata_manager
from src.albion_mcp.core.nats_client import nats_subscriber
from src.albion_mcp.tools import ALL_TOOLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("albion_mcp.server")


@asynccontextmanager
async def server_lifespan(server: MCPServer):
    """Ciclo de vida do servidor MCP."""
    logger.info("Inicializando servidor Albion Online Market Intelligence MCP...")
    # Carrega metadados e nomes em PT-BR
    metadata_manager.ensure_data_loaded()

    # Inicia conexão com NATS Firehose em segundo plano
    nats_task = asyncio.create_task(nats_subscriber.start())
    try:
        yield
    finally:
        logger.info("Encerrando servidor MCP...")
        await nats_subscriber.stop()
        if not nats_task.done():
            nats_task.cancel()


# Cria instância do MCPServer (SDK MCP 2.x)
mcp_server = MCPServer(
    name="albion-market-mcp",
    description=(
        "Servidor MCP para Albion Online. Oferece dados de mercado ao vivo (NATS Firehose), "
        "consultas otimizadas em lote (AODP REST com proteção de rate limit), simulação "
        "de lucros, refino, cascata de insumos e integração analítica Databricks opcional."
    ),
    version="2.0.0",
    lifespan=server_lifespan
)

# Registra todas as ferramentas modulares
for tool_fn in ALL_TOOLS:
    mcp_server.tool()(tool_fn)


def main():
    """Ponto de entrada do executável MCP."""
    transport = "stdio"
    if len(sys.argv) > 1 and sys.argv[1] in ("stdio", "sse", "streamable-http"):
        transport = sys.argv[1]

    logger.info(f"Iniciando Albion Market MCP via transporte '{transport}'...")
    mcp_server.run(transport=transport)


if __name__ == "__main__":
    main()
