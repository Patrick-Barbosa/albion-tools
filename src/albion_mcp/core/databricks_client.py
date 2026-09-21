"""
Cliente Databricks Unity Catalog Statement Execution API (100% Opcional).

Conecta-se ao Databricks SQL Warehouse apenas se as credenciais estiverem
configuradas via variáveis de ambiente (.env ou SO):
- DATABRICKS_HOST
- DATABRICKS_TOKEN
- DATABRICKS_WAREHOUSE_ID
- DATABRICKS_CATALOG (default: 'main')

Se não configurado, o MCP funciona normalmente com o Core em NATS e AODP API,
retornando respostas informativas sem quebrar o fluxo do agente.
"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger("albion_mcp.databricks")

DEFAULT_CATALOG = "main"
GOLD_SCHEMA = "gold"
SILVER_SCHEMA = "silver"


class DatabricksClient:
    def __init__(self):
        self.host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        self.token = os.getenv("DATABRICKS_TOKEN", "")
        self.warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
        self.catalog = os.getenv("DATABRICKS_CATALOG", DEFAULT_CATALOG)

    def is_configured(self) -> bool:
        """Verifica se o Databricks possui credenciais válidas preenchidas."""
        return bool(self.host and self.token and self.warehouse_id)

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status da integração Databricks."""
        configured = self.is_configured()
        return {
            "configured": configured,
            "status": "available" if configured else "disabled_optional",
            "host": self.host if configured else None,
            "warehouse_id": self.warehouse_id if configured else None,
            "catalog": self.catalog if configured else None,
            "message": (
                "Databricks configurado e pronto para consultas analíticas."
                if configured else
                "Databricks não configurado (opcional). O MCP opera com o Core NATS Firehose e AODP REST API."
            )
        }

    async def execute_query(self, sql: str, max_wait_seconds: int = 40) -> Dict[str, Any]:
        """
        Executa uma consulta SQL no Databricks SQL Warehouse via Statement Execution API.
        Caso não esteja configurado, retorna status amigável.
        """
        if not self.is_configured():
            return {
                "success": False,
                "configured": False,
                "error": "Databricks não configurado no ambiente (.env). Esta funcionalidade é opcional.",
                "rows": []
            }

        url = f"{self.host}/api/2.0/sql/statements"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "warehouse_id": self.warehouse_id,
            "statement": sql,
            "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE",
            "catalog": self.catalog
        }

        async with httpx.AsyncClient(timeout=float(max_wait_seconds + 5)) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "configured": True,
                        "error": f"Erro HTTP {resp.status_code} do Databricks: {resp.text[:300]}",
                        "rows": []
                    }

                res_json = resp.json()
                statement_id = res_json.get("statement_id")
                status = res_json.get("status", {}).get("state")

                # Se ainda estiver executando, faz polling curto
                start_time = asyncio.get_event_loop().time()
                while status in ("PENDING", "RUNNING"):
                    if asyncio.get_event_loop().time() - start_time > max_wait_seconds:
                        return {
                            "success": False,
                            "configured": True,
                            "error": f"Tempo limite ({max_wait_seconds}s) excedido para consulta no Databricks.",
                            "statement_id": statement_id,
                            "rows": []
                        }
                    await asyncio.sleep(2.0)
                    poll_resp = await client.get(f"{url}/{statement_id}", headers=headers)
                    if poll_resp.status_code == 200:
                        res_json = poll_resp.json()
                        status = res_json.get("status", {}).get("state")

                if status == "SUCCEEDED":
                    manifest = res_json.get("manifest", {})
                    columns = [col.get("name") for col in manifest.get("schema", {}).get("columns", [])]
                    data_array = res_json.get("result", {}).get("data_array", [])

                    rows = []
                    for row_vals in data_array:
                        rows.append(dict(zip(columns, row_vals)))

                    return {
                        "success": True,
                        "configured": True,
                        "statement_id": statement_id,
                        "total_rows": len(rows),
                        "rows": rows
                    }
                else:
                    err_msg = res_json.get("status", {}).get("error", {}).get("message", "Falha na query SQL.")
                    return {
                        "success": False,
                        "configured": True,
                        "error": err_msg,
                        "statement_id": statement_id,
                        "rows": []
                    }

            except Exception as e:
                logger.error(f"Exceção ao consultar Databricks: {e}")
                return {
                    "success": False,
                    "configured": True,
                    "error": str(e),
                    "rows": []
                }

    async def query_gold_features(
        self,
        item_ids: Optional[List[str]] = None,
        location_id: Optional[int] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Consulta as features consolidadas da tabela Gold (main.gold.history_features)."""
        if not self.is_configured():
            return self.get_status()

        table = f"{self.catalog}.{GOLD_SCHEMA}.history_features"
        clauses = []
        if item_ids:
            quoted_items = ", ".join(f"'{it}'" for it in item_ids)
            clauses.append(f"item_id IN ({quoted_items})")
        if location_id:
            clauses.append(f"location_id = {location_id}")

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
        SELECT item_id, quality_level, location_id, avg_price, avg_daily_sales, total_sold, days_with_sales
        FROM {table}
        {where_str}
        ORDER BY total_sold DESC
        LIMIT {limit}
        """
        return await self.execute_query(sql)


# Instância global
databricks_client = DatabricksClient()
