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
        
    except Exception as e:
        return False, "", str(e)


def print_header(text):
    """Imprime cabeçalho formatado."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")


def print_success(text):
    """Imprime mensagem de sucesso."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Imprime mensagem de erro."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    """Imprime mensagem informativa."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def print_warning(text):
    """Imprime mensagem de aviso."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


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
        print(output)
        return True
    else:
        print_error("Falha na validação do bundle")
        print(error)
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
    
    # Validar primeiro
    print_info("Validando bundle antes do deploy...")
    if not validate_bundle():
        return False
    
    print()
    print_info(f"Iniciando deploy no ambiente '{target}'...")
    print_warning("Isso pode levar alguns minutos...")
    print()
    
    success, output, error = run_command(
        ["databricks", "bundle", "deploy", "-t", target],
        capture_output=False
    )
    
    if success:
        print()
        print_success(f"Deploy concluído com sucesso no ambiente '{target}'!")
        print()
        print_info("Jobs criados/atualizados:")
        print("  1. bronze_nats_ingestion (24/7 streaming)")
        print("  2. orchestrator (Silver/Gold a cada 10min)")
        print()
        print_info("Próximos passos:")
        print(f"  python deploy.py --run-bronze {target}")
        print(f"  python deploy.py --status {target}")
        return True
    else:
        print()
        print_error("Falha no deploy")
        return False


def run_job_bronze(target="prod"):
    """
    Inicia o job de ingestão Bronze (24/7).
    
    Args:
        target (str): Ambiente alvo
    
    Returns:
        bool: True se job foi iniciado
    """
    print_header("INICIAR JOB BRONZE (24/7)")
    
    print_warning("Este job rodará por 24 horas capturando eventos NATS!")
    print_info("Para parar antes: use a UI do Databricks (Workflows)")
    print()
    
    confirm = input("Confirma iniciar job Bronze? (s/N): ").strip().lower()
    if confirm != 's':
        print_info("Operação cancelada.")
        return False
    
    print()
    print_info("Iniciando job bronze_nats_ingestion...")
    
    success, output, error = run_command(
        ["databricks", "bundle", "run", "bronze_nats_ingestion", "-t", target],
        capture_output=False
    )
    
    if success:
        print()
        print_success("Job Bronze iniciado com sucesso!")
        print()
        print_info("O job está rodando em background no Databricks.")
        print_info("Dados serão ingeridos continuamente na tabela Bronze.")
        print()
        print_info("Monitorar:")
        print(f"  python deploy.py --status {target}")
        print("  Ou via UI: Workflows > Jobs > Bronze NATS Ingestion")
        return True
    else:
        print()
        print_error("Falha ao iniciar job Bronze")
        return False


def run_job_orchestrator(target="prod"):
    """
    Executa o job orquestrador uma vez (teste manual).
    
    Args:
        target (str): Ambiente alvo
    
    Returns:
        bool: True se job foi executado
    """
    print_header("EXECUTAR JOB ORQUESTRADOR (TESTE MANUAL)")
    
    print_info("Este job processa Bronze → Silver → Gold")
    print_info("Normalmente roda automaticamente a cada 10 minutos")
    print()
    
    confirm = input("Confirma executar job Orquestrador? (s/N): ").strip().lower()
    if confirm != 's':
        print_info("Operação cancelada.")
        return False
    
    print()
    print_info("Executando job orchestrator...")
    
    success, output, error = run_command(
        ["databricks", "bundle", "run", "orchestrator", "-t", target],
        capture_output=False
    )
    
    if success:
        print()
        print_success("Job Orquestrador executado com sucesso!")
        print()
        print_info("Dados processados:")
        print("  Bronze → Silver (curado)")
        print("  Silver → Gold (agregado)")
        return True
    else:
        print()
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
    
    print_info("Listando jobs do bundle...")
    print()
    
    # Listar jobs do workspace
    success, output, error = run_command(
        ["databricks", "jobs", "list", "--output", "json"]
    )
    
    if not success:
        print_error("Falha ao listar jobs")
        print(error)
        return False
    
    try:
        jobs = json.loads(output)
        
        # Filtrar jobs do bundle
        bundle_jobs = [
            job for job in jobs.get('jobs', [])
            if f"[{target}]" in job.get('settings', {}).get('name', '')
        ]
        
        if not bundle_jobs:
            print_warning(f"Nenhum job encontrado para o ambiente '{target}'")
            print_info("Execute o deploy primeiro:")
            print(f"  python deploy.py --deploy {target}")
            return False
        
        print_success(f"Encontrados {len(bundle_jobs)} job(s):\n")
        
        for job in bundle_jobs:
            job_id = job.get('job_id')
            name = job.get('settings', {}).get('name', 'N/A')
            
            print(f"{Colors.BOLD}{name}{Colors.END}")
            print(f"  Job ID: {job_id}")
            
            # Pegar últimas runs
            success_run, output_run, _ = run_command(
                ["databricks", "jobs", "list-runs", "--job-id", str(job_id), "--limit", "5", "--output", "json"]
            )
            
            if success_run:
                try:
                    runs_data = json.loads(output_run)
                    runs = runs_data.get('runs', [])
                    
                    if runs:
                        latest_run = runs[0]
                        state = latest_run.get('state', {}).get('life_cycle_state', 'N/A')
                        result = latest_run.get('state', {}).get('result_state', 'N/A')
                        
                        state_emoji = {
                            'RUNNING': '🟢',
                            'TERMINATED': '✅' if result == 'SUCCESS' else '❌',
                            'PENDING': '🟡',
                        }.get(state, '❓')
                        
                        print(f"  Status: {state_emoji} {state}")
                        if state == 'TERMINATED':
                            print(f"  Resultado: {result}")
                        print(f"  Últimas {len(runs)} runs disponíveis")
                    else:
                        print("  Status: Nunca executado")
                except:
                    print("  Status: N/A")
            
            print()
        
        return True
        
    except json.JSONDecodeError:
        print_error("Falha ao processar resposta da API")
        return False


def main():
    """Função principal."""
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
    
    # Se nenhum argumento, deploy prod
    if len(sys.argv) == 1:
        success = deploy_bundle("prod")
        return
    
    try:
        args = parser.parse_args()
    except SystemExit:
        # Em ambiente notebook, argparse pode falhar
        # Nesses casos, fazer deploy prod por padrão
        success = deploy_bundle("prod")
        return
    
    # Executar ação solicitada
    success = True
    
    if args.validate:
        success = validate_bundle()
    
    if args.deploy:
        success = deploy_bundle(args.deploy)
    
    if args.run_bronze:
        success = run_job_bronze(args.run_bronze)
    
    if args.run_orchestrator:
        success = run_job_orchestrator(args.run_orchestrator)
    
    if args.status:
        success = show_status(args.status)
    
    return


if __name__ == "__main__":
    main()
