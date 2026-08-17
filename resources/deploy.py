#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Script - Albion Market Analysis
========================================

Script para deploy e gerenciamento de jobs via Databricks Asset Bundles (DABs).

Uso:
    python deploy.py --validate          # Apenas validar configuração
    python deploy.py --deploy dev        # Deploy no ambiente dev
    python deploy.py --deploy prod       # Deploy no ambiente prod
    python deploy.py --run-bronze prod   # Rodar job Bronze (24/7)
    python deploy.py --run-orchestrator prod  # Rodar job Orquestrador (1x)
    python deploy.py --status prod       # Ver status dos jobs
"""

import subprocess
import sys
import argparse
import json
import os
from pathlib import Path

# Reconfigura stdout/stderr para UTF-8 no Windows para evitar UnicodeEncodeError com emojis
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
            # Fallback final: remover caracteres não-ASCII se tudo mais falhar
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
        # Check if IPython is active in namespace
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
            safe_print("  • Para executar a ingestão DIRETAMENTE neste notebook Databricks:")
            safe_print("      %run ../app/src/scripts/bronze_nats_control.py")
            safe_print("      ou:")
            safe_print("      from app.src.scripts.bronze_nats_control import start_ingestion")
            safe_print("      start_ingestion()")
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
    # Começar do diretório do script
    # Em ambientes notebook, __file__ pode não estar definido
    try:
        current = Path(__file__).resolve().parent
    except NameError:
        # Em notebook, usar diretório de trabalho atual
        current = Path.cwd()
    
    # Subir até encontrar databricks.yml (máximo 5 níveis)
    for _ in range(5):
        config_file = current / "databricks.yml"
        if config_file.exists():
            return current
        
        # Subir um nível
        parent = current.parent
        if parent == current:  # Chegou na raiz do sistema
            break
        current = parent
    
    raise FileNotFoundError(
        "Arquivo databricks.yml não encontrado. "
        "Execute este script de dentro de um projeto DABs."
    )


def validate_bundle():
    """
    Valida a configuração do bundle.
    
    Returns:
        bool: True se validação passou
    """
    print_header("VALIDANDO BUNDLE")
    
    if not check_databricks_cli():
        return False

    # Encontrar e mudar para o diretório raiz do bundle
    try:
        bundle_root = find_bundle_root()
        print_info(f"Bundle root: {bundle_root}")
        os.chdir(bundle_root)
    except FileNotFoundError as e:
        print_error(str(e))
        return False
    
    print_info("Validando configuração do bundle...")
    
    success, output, error = run_command(["databricks", "bundle", "validate"])
    
    if success:
        print_success("Bundle validado com sucesso!")
        safe_print(output)
        return True
    else:
        print_error("Falha na validação do bundle")
        safe_print(error)
        return False


def deploy_bundle(target="dev"):
    """
    Faz deploy do bundle para o ambiente especificado.
    
    Args:
        target (str): Ambiente alvo (dev ou prod)
    
    Returns:
        bool: True se deploy foi bem sucedido
    """
    print_header(f"DEPLOY - AMBIENTE: {target.upper()}")
    
    if not check_databricks_cli():
        return False

    # Validar primeiro
    print_info("Validando bundle antes do deploy...")
    if not validate_bundle():
        return False
    
    safe_print()
    print_info(f"Iniciando deploy no ambiente '{target}'...")
    print_warning("Isso pode levar alguns minutos...")
    safe_print()
    
    success, output, error = run_command(
        ["databricks", "bundle", "deploy", "-t", target],
        capture_output=False
    )
    
    if success:
        safe_print()
        print_success(f"Deploy concluído com sucesso no ambiente '{target}'!")
        safe_print()
        print_info("Jobs criados/atualizados:")
        safe_print("  1. bronze_nats_ingestion (24/7 streaming)")
        safe_print("  2. orchestrator (Silver/Gold a cada 10min)")
        safe_print()
        print_info("Próximos passos:")
        safe_print(f"  python deploy.py --run-bronze {target}")
        safe_print(f"  python deploy.py --status {target}")
        return True
    else:
        safe_print()
        print_error("Falha no deploy")
        return False


def run_job_bronze(target="prod", auto_confirm=False):
    """
    Inicia o job de ingestão Bronze (24/7).
    
    Args:
        target (str): Ambiente alvo
        auto_confirm (bool): Se True, ignora prompt de confirmação
    
    Returns:
        bool: True se job foi iniciado
    """
    print_header("INICIAR JOB BRONZE (24/7)")
    
    if not check_databricks_cli():
        return False

    print_warning("Este job rodará por 24 horas capturando eventos NATS!")
    print_info("Para parar antes: use a UI do Databricks (Workflows)")
    safe_print()
    
    if not auto_confirm:
        try:
            confirm = input("Confirma iniciar job Bronze? (s/N): ").strip().lower()
            if confirm != 's':
                print_info("Operação cancelada.")
                return False
        except (EOFError, KeyboardInterrupt):
            print_info("Operação cancelada.")
            return False
    
    safe_print()
    print_info("Iniciando job bronze_nats_ingestion...")
    
    success, output, error = run_command(
        ["databricks", "bundle", "run", "bronze_nats_ingestion", "-t", target],
        capture_output=False
    )
    
    if success:
        safe_print()
        print_success("Job Bronze iniciado com sucesso!")
        safe_print()
        print_info("O job está rodando em background no Databricks.")
        print_info("Dados serão ingeridos continuamente na tabela Bronze.")
        safe_print()
        print_info("Monitorar:")
        safe_print(f"  python deploy.py --status {target}")
        safe_print("  Ou via UI: Workflows > Jobs > Bronze NATS Ingestion")
        return True
    else:
        safe_print()
        print_error("Falha ao iniciar job Bronze")
        return False


def run_job_orchestrator(target="prod", auto_confirm=False):
    """
    Executa o job orquestrador uma vez (teste manual).
    
    Args:
        target (str): Ambiente alvo
        auto_confirm (bool): Se True, ignora prompt de confirmação
    
    Returns:
        bool: True se job foi executado
    """
    print_header("EXECUTAR JOB ORQUESTRADOR (TESTE MANUAL)")
    
    if not check_databricks_cli():
        return False

    print_info("Este job processa Bronze → Silver → Gold")
    print_info("Normalmente roda automaticamente a cada 10 minutos")
    safe_print()
    
    if not auto_confirm:
        try:
            confirm = input("Confirma executar job Orquestrador? (s/N): ").strip().lower()
            if confirm != 's':
                print_info("Operação cancelada.")
                return False
        except (EOFError, KeyboardInterrupt):
            print_info("Operação cancelada.")
            return False
    
    safe_print()
    print_info("Executando job orchestrator...")
    
    success, output, error = run_command(
        ["databricks", "bundle", "run", "orchestrator", "-t", target],
        capture_output=False
    )
    
    if success:
        safe_print()
        print_success("Job Orquestrador executado com sucesso!")
        safe_print()
        print_info("Dados processados:")
        safe_print("  Bronze → Silver (curado)")
        safe_print("  Silver → Gold (agregado)")
        return True
    else:
        safe_print()
        print_error("Falha ao executar job Orquestrador")
        return False


def show_status(target="prod"):
    """
    Mostra status dos jobs no ambiente.
    
    Args:
        target (str): Ambiente alvo
    
    Returns:
        bool: True se conseguiu obter status
    """
    print_header(f"STATUS DOS JOBS - AMBIENTE: {target.upper()}")
    
    if not check_databricks_cli():
        return False

    print_info("Listando jobs do bundle...")
    safe_print()
    
    # Listar jobs do workspace
    success, output, error = run_command(
        ["databricks", "jobs", "list", "--output", "json"]
    )
    
    if not success:
        print_error("Falha ao listar jobs")
        safe_print(error)
        return False
    
    try:
        jobs = json.loads(output)
        
        # Lista de jobs retornada pela API (pode estar na chave 'jobs' ou ser lista direta)
        jobs_list = jobs.get('jobs', []) if isinstance(jobs, dict) else jobs
        
        # Filtrar jobs do bundle
        bundle_jobs = [
            job for job in jobs_list
            if f"[{target}]" in job.get('settings', {}).get('name', '')
        ]
        
        if not bundle_jobs:
            print_warning(f"Nenhum job encontrado para o ambiente '{target}'")
            print_info("Execute o deploy primeiro:")
            safe_print(f"  python deploy.py --deploy {target}")
            return False
        
        print_success(f"Encontrados {len(bundle_jobs)} job(s):\n")
        
        for job in bundle_jobs:
            job_id = job.get('job_id')
            name = job.get('settings', {}).get('name', 'N/A')
            
            safe_print(f"{Colors.BOLD}{name}{Colors.END}")
            safe_print(f"  Job ID: {job_id}")
            
            # Pegar últimas runs
            success_run, output_run, _ = run_command(
                ["databricks", "jobs", "list-runs", "--job-id", str(job_id), "--limit", "5", "--output", "json"]
            )
            
            if success_run:
                try:
                    runs_data = json.loads(output_run)
                    runs = runs_data.get('runs', []) if isinstance(runs_data, dict) else runs_data
                    
                    if runs:
                        latest_run = runs[0]
                        state = latest_run.get('state', {}).get('life_cycle_state', 'N/A')
                        result = latest_run.get('state', {}).get('result_state', 'N/A')
                        
                        state_emoji = {
                            'RUNNING': '🟢',
                            'TERMINATED': '✅' if result == 'SUCCESS' else '❌',
                            'PENDING': '🟡',
                        }.get(state, '❓')
                        
                        safe_print(f"  Status: {state_emoji} {state}")
                        if state == 'TERMINATED':
                            safe_print(f"  Resultado: {result}")
                        safe_print(f"  Últimas {len(runs)} runs disponíveis")
                    else:
                        safe_print("  Status: Nunca executado")
                except Exception:
                    safe_print("  Status: N/A")
            
            safe_print()
        
        return True
        
    except json.JSONDecodeError:
        print_error("Falha ao processar resposta da API do Databricks")
        return False


def main():
    """Função principal."""
    in_notebook = is_notebook_environment()

    parser = argparse.ArgumentParser(
        description='Deploy e gerenciamento de jobs - Albion Market Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python deploy.py --validate
  python deploy.py --deploy prod
  python deploy.py --run-bronze prod
  python deploy.py --status prod
        """
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validar configuração do bundle'
    )
    
    parser.add_argument(
        '--deploy',
        metavar='TARGET',
        choices=['dev', 'prod'],
        help='Deploy no ambiente especificado (dev ou prod)'
    )
    
    parser.add_argument(
        '--run-bronze',
        metavar='TARGET',
        choices=['dev', 'prod'],
        help='Iniciar job Bronze 24/7 no ambiente especificado'
    )
    
    parser.add_argument(
        '--run-orchestrator',
        metavar='TARGET',
        choices=['dev', 'prod'],
        help='Executar job Orquestrador uma vez no ambiente especificado'
    )
    
    parser.add_argument(
        '--status',
        metavar='TARGET',
        choices=['dev', 'prod'],
        help='Ver status dos jobs no ambiente especificado'
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Confirmar execuções automaticamente sem prompt interativo'
    )
    
    # Parse com parse_known_args para ignorar flags do kernel (ex: -f /path/to/connection.json)
    try:
        args, unknown = parser.parse_known_args()
    except SystemExit as e:
        if e.code == 0:
            return
        sys.exit(e.code)
    
    has_action = any([args.validate, args.deploy, args.run_bronze, args.run_orchestrator, args.status])
    
    # Se estiver rodando dentro do notebook do Databricks sem argumentos CLI específicos
    if in_notebook and not has_action:
        print_header("ALBION MARKET ANALYSIS - DEPLOY HELPER")
        print_info("Ambiente de Notebook / Databricks detectado.")
        safe_print("Opções de uso:")
        safe_print("  1. Ingestão direta no Databricks (Recomendado no Notebook):")
        safe_print("     %run ../app/src/scripts/bronze_nats_control.py")
        safe_print("     ou:")
        safe_print("     from app.src.scripts.bronze_nats_control import start_ingestion, get_status")
        safe_print("     start_ingestion()")
        safe_print()
        safe_print("  2. Deploy via Databricks Asset Bundles (DABs):")
        safe_print("     Execute no seu terminal LOCAL (computador/workstation):")
        safe_print("     python resources/deploy.py --deploy dev")
        safe_print("     python resources/deploy.py --run-bronze dev")
        safe_print()
        return

    # Se nenhum argumento no terminal CLI, deploy prod por padrão
    if not has_action and len(sys.argv) == 1:
        deploy_bundle("prod")
        return
    
    # Executar ação solicitada
    if args.validate:
        validate_bundle()
    
    if args.deploy:
        deploy_bundle(args.deploy)
    
    if args.run_bronze:
        run_job_bronze(args.run_bronze, auto_confirm=args.yes)
    
    if args.run_orchestrator:
        run_job_orchestrator(args.run_orchestrator, auto_confirm=args.yes)
    
    if args.status:
        show_status(args.status)
    
    return


if __name__ == "__main__":
    main()
