"""
Núcleo compartilhado das skills Albion Online — 100% biblioteca padrão.

Uso típico dentro dos scripts de skill (o núcleo fica ao lado da pasta `scripts/`):

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _albion_core import market, economics

No repositório, a fonte de verdade fica em `skills/_albion_core/`.
Nas skills publicadas via `npx skills add`, cada skill carrega a própria cópia
vendorizada (gerada por `tools/sync_core.py`).

Módulos:
    http         cliente AODP (urllib) com batching, cache e rate limit
    market       cotações, histórico, ouro e quota
    items        busca e ficha técnica de itens
    economics    impostos, encantamento, arbitragem
    refining     refino e cascata
    pareto       curva 80/20 de prata diária
    builds       otimização de build por tier equivalente
    anti_phantom breakeven, auditoria de cotação, knapsack, reroll, carga
    hearts       transporte de facção, ciclo de corações e capas
    metadata     catálogo PT-BR/EN
    calculator   fórmulas fiscais oficiais
"""

from . import (  # noqa: F401
    anti_phantom,
    builds,
    calculator,
    economics,
    hearts,
    http,
    items,
    market,
    metadata,
    pareto,
    refining,
)

__all__ = [
    "anti_phantom",
    "builds",
    "calculator",
    "economics",
    "hearts",
    "http",
    "items",
    "market",
    "metadata",
    "pareto",
    "refining",
]
