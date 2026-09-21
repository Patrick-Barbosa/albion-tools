"""
Teste de Integração End-to-End do Servidor MCP Albion via protocolo stdio oficial.

Inicia o processo `python -m src.albion_mcp` como subprocesso MCP,
conecta via ClientSession através de stdin/stdout (JSON-RPC),
faz o handshake initialize, lista as 15 ferramentas e executa chamadas
reais aos tools (albion_search_items, albion_get_api_quota_status, albion_calculate_tax_and_fees).
"""

import sys
import os
import asyncio

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession


async def _run_e2e():
    print("🚀 [1/5] Configurando parâmetros do subprocesso MCP (stdio)...")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.albion_mcp"],
        cwd=REPO_ROOT
    )

    print("🔌 [2/5] Conectando ao servidor MCP via stdio_client...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("🤝 [3/5] Executando handshake initialize()...")
            init_result = await session.initialize()
            print("✅ Handshake concluído com sucesso!")
            print(f"   - Nome do Servidor: {init_result.server_info.name}")
            print(f"   - Versão do Servidor: {init_result.server_info.version}")
            print(f"   - Versão do Protocolo: {init_result.protocol_version}")

            print("\n📋 [4/5] Listando ferramentas disponíveis (list_tools)...")
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"✅ Total de {len(tool_names)} ferramentas descobertas pelo protocolo MCP:")
            for name in tool_names:
                print(f"   * {name}")
            assert len(tool_names) >= 22, f"Esperado pelo menos 22 ferramentas, encontrado {len(tool_names)}"
            assert "albion_optimize_budget_build" in tool_names

            print("\n⚡ [5/5] Invocando ferramentas via JSON-RPC (call_tool)...")

            # 1. albion_search_items
            print("  -> Chamando albion_search_items('Espada', tier='T5')...")
            call_res1 = await session.call_tool("albion_search_items", {"query": "Espada", "tier": "T5", "limit": 3})
            print(f"     Resposta recebida: {len(call_res1.content)} bloco(s) de conteúdo.")
            assert len(call_res1.content) > 0

            # 2. albion_get_api_quota_status
            print("  -> Chamando albion_get_api_quota_status()...")
            call_res2 = await session.call_tool("albion_get_api_quota_status", {})
            assert len(call_res2.content) > 0

            # 3. albion_calculate_tax_and_fees
            print("  -> Chamando albion_calculate_tax_and_fees(buy_price=100000, sell_price=150000)...")
            call_res3 = await session.call_tool("albion_calculate_tax_and_fees", {
                "buy_price": 100000,
                "sell_price": 150000,
                "has_premium": True
            })
            assert len(call_res3.content) > 0

            # 4. albion_calculate_breakeven_price (Anti-Alucinação)
            print("  -> Chamando albion_calculate_breakeven_price(buy_price=100000, has_premium=True)...")
            call_res4 = await session.call_tool("albion_calculate_breakeven_price", {
                "buy_price": 100000,
                "is_buy_order": True,
                "has_premium": True
            })
            assert len(call_res4.content) > 0

            # 5. albion_optimize_budget_build (Otimizador de Builds)
            print("  -> Chamando albion_optimize_budget_build(['Machado de Guerra'], target_tier_equivalent=7, city='Lymhurst')...")
            call_res5 = await session.call_tool("albion_optimize_budget_build", {
                "items": ["Machado de Guerra"],
                "target_tier_equivalent": 7,
                "city": "Lymhurst",
                "price_mode": "history"
            })
            assert len(call_res5.content) > 0

            print("\n🎉 Todos os testes de protocolo MCP STDIO executados e validados com 100% de sucesso!")


def test_mcp_server_e2e():
    """Função de teste executável tanto pelo pytest quanto via CLI direta."""
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    test_mcp_server_e2e()
