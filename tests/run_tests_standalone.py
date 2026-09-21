"""
Runner autônomo de testes para execução sem dependência externa do pytest.
Executa todos os testes unitários e de integração das novas mecânicas de Logística e Facção.
"""

import sys
import os
import inspect
import asyncio

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Inject dummy pytest if pytest is not installed in the environment
try:
    import pytest
except ImportError:
    class DummyMark:
        def asyncio(self, f):
            return f
    class DummyRaises:
        def __init__(self, expected_exc):
            self.expected_exc = expected_exc
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.expected_exc}, but no exception was raised.")
            return issubclass(exc_type, self.expected_exc)
    class DummyPytest:
        mark = DummyMark()
        raises = DummyRaises
    sys.modules['pytest'] = DummyPytest()

import tests.test_calculator as t_calc
import tests.test_metadata as t_meta
import tests.test_rate_limiter as t_rate
import tests.test_anti_hallucination as t_anti
import tests.test_build_optimizer as t_build
import tests.test_mcp_tools as t_tools
import tests.test_loadout_optimizer as t_loadout
import tests.test_faction_transport as t_faction
import tests.test_cape_crafting as t_cape
import tests.test_faction_mcp_tools as t_mcp

MODULES_TO_TEST = [
    ("Core: Regras Fiscais e Financeiras", t_calc),
    ("Core: Metadados PT-BR e Resolução", t_meta),
    ("Core: Rate Limiter & Quotas", t_rate),
    ("Core: Motor Otimizador de Builds", t_build),
    ("Core: Ferramentas Anti-Alucinação & Transmutação", t_anti),
    ("Core: Ferramentas Gerais do MCP", t_tools),
    ("Motor 1: Loadout Optimizer", t_loadout),
    ("Motor 2: Faction Transport", t_faction),
    ("Cadeia Downstream: Cape Crafting", t_cape),
    ("Ferramentas MCP: Faction & Logistics", t_mcp)
]



def run_all_tests():
    total_run = 0
    total_passed = 0
    failures = []

    print("=" * 70)
    print("🚀 INICIANDO BATERIA DE TESTES: MOTORES DE LOGÍSTICA & TRANSPORTE DE FACÇÃO")
    print("=" * 70)

    for mod_title, mod in MODULES_TO_TEST:
        print(f"\n📂 [{mod_title}]")
        for attr_name in dir(mod):
            if attr_name.startswith("test_"):
                fn = getattr(mod, attr_name)
                if callable(fn):
                    total_run += 1
                    try:
                        if asyncio.iscoroutinefunction(fn):
                            asyncio.run(fn())
                        else:
                            fn()
                        total_passed += 1
                        print(f"  ✅ {attr_name}")
                    except Exception as e:
                        failures.append((mod_title, attr_name, str(e)))
                        print(f"  ❌ {attr_name} -> ERRO: {e}")

    print("\n" + "=" * 70)
    print(f"📊 RESULTADO FINAL: {total_passed}/{total_run} testes passaram!")
    if failures:
        print(f"⚠️  {len(failures)} FALHAS ENCONTRADAS:")
        for mod_title, name, err in failures:
            print(f"   - [{mod_title}] {name}: {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print("🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO!")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
