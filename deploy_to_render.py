import os
import sys
import subprocess
import time
import webbrowser
import json
import requests
import re

def check_git():
    """Verificar se o Git está instalado"""
    try:
        subprocess.check_output(["git", "--version"])
        return True
    except:
        print("Git não está instalado ou não está no PATH.")
        print("Por favor, instale o Git: https://git-scm.com/downloads")
        return False

def init_git():
    """Inicializar repositório Git se necessário"""
    if not os.path.exists(".git"):
        print("\nInicializando repositório Git...")
        subprocess.call(["git", "init"])
        return True
    return False

def commit_changes():
    """Adicionar e commitar alterações"""
    print("\nAdicionando arquivos ao Git...")
    subprocess.call(["git", "add", "."])
    
    print("\nCommitando alterações...")
    subprocess.call(["git", "commit", "-m", "Prepare for Render deployment"])

def create_github_repo():
    """Criar um repositório no GitHub"""
    print("\n" + "="*60)
    print("Para fazer o deploy no Render, precisamos primeiro enviar o código para o GitHub.")
    print("="*60)
    
    # Verificar se o usuário já tem um repositório configurado
    result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
    if "origin" in result.stdout:
        print("\nVocê já tem um repositório remoto configurado:")
        print(result.stdout)
        use_existing = input("Deseja usar este repositório? (s/n): ").strip().lower()
        if use_existing == 's':
            # Extrair a URL do repositório
            for line in result.stdout.split('\n'):
                if "origin" in line and "(push)" in line:
                    url = line.split()[1]
                    # Converter URL SSH para HTTPS se necessário
                    if url.startswith("git@github.com:"):
                        url = url.replace("git@github.com:", "https://github.com/")
                        url = url.replace(".git", "")
                    return url
    
    print("\nVocê precisará criar um repositório no GitHub.")
    print("1. Acesse https://github.com/new")
    print("2. Dê um nome ao seu repositório (ex: 'quiz-app')")
    print("3. Deixe-o público")
    print("4. Não inicialize com README, .gitignore ou licença")
    print("5. Clique em 'Create repository'")
    
    input("\nPressione Enter quando tiver criado o repositório...")
    
    repo_url = input("\nCole a URL do repositório que você acabou de criar: ").strip()
    
    # Adicionar o remote
    subprocess.call(["git", "remote", "add", "origin", repo_url])
    
    return repo_url

def push_to_github():
    """Enviar código para o GitHub"""
    print("\nEnviando código para o GitHub...")
    subprocess.call(["git", "push", "-u", "origin", "master"])

def deploy_to_render(repo_url):
    """Abrir o Render para deploy"""
    render_url = "https://dashboard.render.com/new/web-service"
    
    # Extrair nome do usuário e nome do repositório da URL
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if match:
        github_user = match.group(1)
        repo_name = match.group(2)
        
        # Construir URL para deploy direto
        render_deploy_url = f"{render_url}?type=web&repo=https://github.com/{github_user}/{repo_name}&branch=master&name={repo_name}"
        
        print("\n" + "="*60)
        print("Instruções para deploy no Render:")
        print("="*60)
        print("1. Abriremos o Render no seu navegador")
        print("2. Faça login ou crie uma conta se necessário")
        print("3. Conecte sua conta GitHub se solicitado")
        print("4. Na página de configuração do serviço, defina:")
        print("   - Nome: escolha um nome para seu app")
        print("   - Região: escolha a mais próxima de você")
        print("   - Branch: master")
        print("   - Comando de Build: pip install -r requirements.txt")
        print("   - Comando de Start: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app")
        print("   - Plano: Free")
        print("5. Clique em 'Create Web Service'")
        print("="*60)
        
        input("\nPressione Enter para abrir o Render no navegador...")
        webbrowser.open(render_deploy_url)
        
        print("\nO deploy está sendo iniciado no Render.")
        print("O processo leva alguns minutos. Você pode acompanhar o progresso no painel do Render.")
        
        app_url = input("\nQuando o deploy estiver concluído, cole a URL do seu app aqui: ").strip()
        
        print(f"\nSeu Quiz está disponível em: {app_url}")
        print("\nDeploy concluído com sucesso!")
        print("="*60)
    else:
        print("\nNão foi possível extrair informações do repositório da URL fornecida.")
        print("Por favor, acesse https://dashboard.render.com/new/web-service manualmente")
        print("e siga as instruções para conectar seu repositório GitHub.")

def main():
    print("=" * 60)
    print("Assistente de Deploy do Quiz para Render.com")
    print("=" * 60)
    
    # Verificar requisitos
    if not check_git():
        return
    
    # Inicializar Git
    init_git()
    
    # Commitar alterações
    commit_changes()
    
    # Criar/usar repositório GitHub
    repo_url = create_github_repo()
    if not repo_url:
        print("Não foi possível obter a URL do repositório GitHub.")
        return
    
    # Enviar para o GitHub
    push_to_github()
    
    # Deploy no Render
    deploy_to_render(repo_url)

if __name__ == "__main__":
    main()
