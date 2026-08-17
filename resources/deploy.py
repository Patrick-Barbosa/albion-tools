#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Script - Albion Market Analysis
========================================

Script para validação e deploy de pipelines via Databricks Asset Bundles (DABs) em Produção.

Uso:
    python deploy.py             # Valida e faz deploy no ambiente PROD
    python deploy.py --deploy    # Valida e faz deploy no ambiente PROD
    python deploy.py --validate  # Apenas validar a configuração do bundle
"""

import subprocess
import sys
import argparse
import os
from pathlib import Path

# Reconfigura stdout/stderr para UTF-8 no Windows para evitar UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def safe_print(text=""):
    """Imprime texto garantindo compatibilidade de encoding."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
        try:
            encoded = text.encode(encoding, errors='replace')
            print(encoded.decode(encoding, errors='replace'))
        except Exception:
            print(text.encode('ascii', errors='replace').decode('ascii'))


class Colors:
    """ANSI color codes para output colorido."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def run_command(cmd, capture_output=True):
    """
    Executa comando shell e retorna resultado.
    
    Args:
        cmd (list): Comando e argumentos
        capture_output (bool): Se True, captura output
    
    Returns:
        tuple: (success: bool, output: str, error: str)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=False
        )
        
        success = result.returncode == 0
        output = result.stdout if capture_output else ""
        error = result.stderr if capture_output else ""
        
        return success, output, error
        
    except FileNotFoundError:
        return False, "", f"Comando '{cmd[0]}' não foi encontrado no sistema."
    except Exception as e:
        return False, "", str(e)


def print_header(text):
    """Imprime cabeçalho formatado."""
    safe_print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    safe_print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.END}")
    safe_print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")


def print_success(text):
    """Imprime mensagem de sucesso."""
    safe_print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Imprime mensagem de erro."""
    safe_print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    """Imprime mensagem informativa."""
    safe_print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def print_warning(text):
    """Imprime mensagem de aviso."""
    safe_print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def is_in_databricks():
    """Detecta se o script está rodando dentro do Databricks."""
    return (
        'DATABRICKS_RUNTIME_VERSION' in os.environ
        or 'DATABRICKS_HOST' in os.environ
        or any('db_ipykernel' in str(arg) or 'sandboxapi' in str(arg) for arg in sys.argv)
    )


def is_notebook_environment():
    """Detecta se o script está rodando dentro de um notebook (Databricks / Jupyter / IPython)."""
    if is_in_databricks():
        return True
    if any('ipykernel' in str(arg) or 'jupyter' in str(arg) for arg in sys.argv):
        return True
    try:
        get_ipython()  # noqa: F821
        return True
    except NameError:
        return False


def check_databricks_cli():
    """
    Verifica se o CLI do Databricks está instalado no ambiente.
    
    Returns:
        bool: True se databricks CLI estiver acessível.
    """
    success, output, error = run_command(["databricks", "--version"])
    if not success:
        print_error("Databricks CLI não foi encontrado no ambiente atual.")
        if is_in_databricks():
            print_info("Detectado que você está executando dentro de um Notebook/Cluster Databricks.")
            safe_print("  • O script 'deploy.py' (DABs) foi feito para gerenciar o bundle a partir da sua máquina LOCAL ou CI/CD.")
            safe_print("  • Para executar os pipelines diretamente neste notebook Databricks:")
            safe_print("      %run ../app/src/scripts/bronze_nats_control.py")
            safe_print("  • Se quiser instalar o Databricks CLI no cluster Databricks, execute em uma célula %sh:")
            safe_print("      %sh curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh\n")
        else:
            print_info("Para instalar o Databricks CLI na sua máquina local:")
            safe_print("  • Windows (winget): winget install Databricks.CLI")
            safe_print("  • Documentação oficial: https://docs.databricks.com/dev-tools/cli/index.html")
            safe_print("  • Após a instalação, configure o acesso executando: databricks configure\n")
        return False
    return True


def find_bundle_root():
    """
    Encontra o diretório raiz do bundle (onde está databricks.yml).
    
    Returns:
        Path: Caminho absoluto do diretório raiz do bundle
    
    Raises:
        FileNotFoundError: Se databricks.yml não for encontrado
    """
    try:
        current = Path(__file__).resolve().parent
    except NameError:
        current = Path.cwd()
    
    for _ in range(5):
        config_file = current / "databricks.yml"
        if config_file.exists():
            return current
        
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    raise FileNotFoundError(
        "Arquivo databricks.yml não encontrado. "
        "Execute este script de dentro da raiz do repositório."
    )


def validate_bundle():
    """
    Valida a configuração do bundle para Produção.
    
    Returns:
        bool: True se validação passou
    """
    print_header("VALIDANDO BUNDLE - PROD")
    
    if not check_databricks_cli():
        return False

    try:
        bundle_root = find_bundle_root()
        print_info(f"Bundle root: {bundle_root}")
        os.chdir(bundle_root)
    except FileNotFoundError as e:
        print_error(str(e))
        return False
    
    print_info("Validando configuração do bundle (target: prod)...")
    
    success, output, error = run_command(["databricks", "bundle", "validate", "-t", "prod"])
    
    if success:
        print_success("Bundle validado com sucesso para Produção!")
        if output.strip():
            safe_print(output)
        return True
    else:
        print_error("Falha na validação do bundle")
        if error.strip():
            safe_print(error)
        return False


def deploy_bundle():
    """
    Faz deploy das pipelines e jobs para o ambiente de Produção (prod).
    
    Returns:
        bool: True se deploy foi bem sucedido
    """
    print_header("DEPLOY - AMBIENTE: PROD")
    
    if not check_databricks_cli():
        return False

    # 1. Validar primeiro
    print_info("Validando bundle antes do deploy...")
    if not validate_bundle():
        return False
    
    safe_print()
    print_info("Iniciando deploy das pipelines e jobs no ambiente 'prod'...")
    print_warning("Isso pode levar alguns minutos...")
    safe_print()
    
    # 2. Executar deploy
    success, output, error = run_command(
        ["databricks", "bundle", "deploy", "-t", "prod"],
        capture_output=False
    )
    
    if success:
        safe_print()
        print_success("Deploy concluído com sucesso no ambiente 'PROD'!")
        safe_print()
        print_info("Pipelines e recursos implantados:")
        safe_print("  • Pipeline SDP: Albion Online Market Analysis (Bronze → Silver → Gold)")
        safe_print("  • Job Orquestrador: [prod] Albion Market Analysis - Full Orchestration")
        safe_print("  • Job Streaming: [prod] Bronze NATS Ingestion (24/7)")
        safe_print()
        return True
    else:
        safe_print()
        print_error("Falha no deploy do bundle")
        return False


def main():
    """Função principal."""
    in_notebook = is_notebook_environment()

    parser = argparse.ArgumentParser(
        description='Deploy de Pipelines - Albion Market Analysis (PROD)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python deploy.py            # Valida e faz deploy no ambiente PROD
  python deploy.py --deploy   # Valida e faz deploy no ambiente PROD
  python deploy.py --validate # Apenas valida configuração do bundle
        """
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validar configuração do bundle para Produção'
    )
    
    parser.add_argument(
        '--deploy',
        action='store_true',
        help='Fazer deploy das pipelines no ambiente de Produção (prod)'
    )

    try:
        args, unknown = parser.parse_known_args()
    except SystemExit as e:
        if e.code == 0:
            return
        sys.exit(e.code)
    
    has_action = args.validate or args.deploy
    
    # Se estiver rodando dentro do notebook do Databricks sem argumentos CLI específicos
    if in_notebook and not has_action:
        print_header("ALBION MARKET ANALYSIS - DEPLOY HELPER")
        print_info("Ambiente de Notebook / Databricks detectado.")
        safe_print("Opções:")
        safe_print("  1. Execução direta neste Notebook Databricks:")
        safe_print("     %run ../app/src/scripts/bronze_nats_control.py")
        safe_print()
        safe_print("  2. Deploy das pipelines via DABs (PROD):")
        safe_print("     Execute no seu terminal LOCAL (computador/workstation):")
        safe_print("     python resources/deploy.py --deploy")
        safe_print()
        return

    # Se --validate foi especificado explicitamente
    if args.validate and not args.deploy:
        validate_bundle()
        return

    # Por padrão (ou com --deploy), executa validação e deploy em PROD
    deploy_bundle()


if __name__ == "__main__":
    main()
