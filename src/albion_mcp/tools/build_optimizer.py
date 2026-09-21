"""
Ferramenta MCP para Otimização de Builds Econômicas por Tier Equivalente no Albion Online.
"""

from typing import List, Dict, Any, Optional
from ..core.build_optimizer import optimize_budget_build


async def albion_optimize_budget_build(
    items: List[str],
    target_tier_equivalent: int,
    city: str,
    price_mode: str = "live",
    server_region: str = "americas",
    max_quality: int = 2
) -> Dict[str, Any]:
    """
    Identifica a combinação mais barata de equipamentos para atingir um Tier Equivalente desejado.

    Para um determinado nível de poder (ex: Tier 7 equivalente), avalia todas as variações viáveis
    (como 4.3, 5.2, 6.1 e 7.0) comparando os preços reais na cidade escolhida e determinando
    a opção de menor custo para cada peça (arma, cabeça, peitoral, botas, capa, etc.).

    Fórmula de Tier Equivalente (Item Power base):
    - Tier Equivalente = Tier + Nível de Encantamento
    - Exemplo T7 eq: 4.3 (4+3=7), 5.2 (5+2=7), 6.1 (6+1=7), 7.0 (7+0=7)
    - Exemplo T8 eq: 4.4, 5.3, 6.2, 7.1, 8.0
    - Exemplo T6 eq: 4.2, 5.1, 6.0

    Consumo Eficiente da API:
    - Agrupa todas as permutações de todas as peças e executa uma ÚNICA chamada GET em lote,
      respeitando os limites de taxa (rate limiter) e usando cache TTL de 120 segundos.

    Parâmetros:
    - items: Lista de itens que compõem a build. Aceita nomes em português (ex: "Machado de Guerra",
      "Capuz de Caçador", "Casaco de Mercenário", "Botas de Soldado"), nomes em inglês ou IDs técnicos
      (ex: "T4_MAIN_AXE", "T4_ARMOR_LEATHER_SET1").
    - target_tier_equivalent: O nível equivalente desejado em número inteiro (ex: 6, 7, 8).
    - city: Cidade onde o jogador comprará os itens (ex: 'Lymhurst', 'Bridgewatch', 'Fort Sterling',
      'Martlock', 'Thetford', 'Caerleon', 'Brecilien').
    - price_mode: Fonte de preços desejada. Opções:
        * 'live' (padrão): Menor Sell Order ativa no mercado no momento (compra imediata).
        * 'history': Preço médio negociado recentemente (banco histórico SQLite local).
        * 'databricks': Preço médio consolidado da tabela Gold do Databricks (se configurado).
    - server_region: Região do servidor ('americas', 'europe', 'asia'). Padrão: 'americas'.
    - max_quality: Qualidade máxima considerada (1=Normal, 2=Bom, 3=Notável, 4=Excelente, 5=Obra-prima).
      Padrão: 2 (Normal ou Bom, que oferecem praticamente o mesmo IP sem inflação de preço).

    Retorno:
    - Resumo financeiro com custo total otimizado vs custo comprando tudo direto (flat tier).
    - Economia líquida em prata e porcentagem economizada.
    - Detalhamento por slot com a opção recomendada e tabela de todas as variações equivalentes.
    """
    return await optimize_budget_build(
        items=items,
        target_tier_equivalent=target_tier_equivalent,
        city=city,
        price_mode=price_mode,
        server_region=server_region,
        max_quality=max_quality
    )
