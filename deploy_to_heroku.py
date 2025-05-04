import os
import sys
import subprocess
import time
import webbrowser

def check_heroku_cli():
    """Verificar se o Heroku CLI está instalado"""
    try:
        subprocess.check_output(["heroku", "--version"])
        return True
    except:
        print("Heroku CLI não está instalado ou não está no PATH.")
        print("Por favor, instale o Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli")
        return False

def check_git():
    """Verificar se o Git está instalado"""
    try:
        subprocess.check_output(["git", "--version"])
        return True
    except:
        print("Git não está instalado ou não está no PATH.")
        print("Por favor, instale o Git: https://git-scm.com/downloads")
        return False

def heroku_login():
    """Fazer login no Heroku"""
    print("\nFazendo login no Heroku...")
    subprocess.call(["heroku", "login"])

def create_heroku_app():
    """Criar um novo app no Heroku"""
    app_name = input("\nDigite um nome para sua aplicação Heroku (deixe em branco para um nome aleatório): ").strip()
    
    cmd = ["heroku", "create"]
    if app_name:
        cmd.append(app_name)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Erro ao criar aplicação: {result.stderr}")
        return None
    
    # Extrair o nome do app e a URL do output
    lines = result.stdout.strip().split('\n')
    if len(lines) >= 1:
        parts = lines[0].split('|')
        if len(parts) >= 1:
            url = parts[0].strip()
            app_name = url.replace("https://", "").replace(".herokuapp.com", "")
            return app_name, url
    
    print("Não foi possível determinar o nome do app criado.")
    return None

def init_git():
    """Inicializar repositório Git se necessário"""
    if not os.path.exists(".git"):
        print("\nInicializando repositório Git...")
        subprocess.call(["git", "init"])
    
    # Verificar se já existe um remote heroku
    result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
    if "heroku" not in result.stdout:
        app_info = create_heroku_app()
        if not app_info:
            return None
        
        app_name, app_url = app_info
        print(f"\nAplicação criada: {app_url}")
        
        # Adicionar remote heroku
        subprocess.call(["git", "remote", "add", "heroku", f"https://git.heroku.com/{app_name}.git"])
        return app_name
    else:
        # Extrair o nome do app do remote
        for line in result.stdout.split('\n'):
            if "heroku" in line and "(push)" in line:
                url = line.split()[1]
                app_name = url.split('/')[-1].replace(".git", "")
                return app_name
    
    return None

def commit_changes():
    """Adicionar e commitar alterações"""
    print("\nAdicionando arquivos ao Git...")
    subprocess.call(["git", "add", "."])
    
    print("\nCommitando alterações...")
    subprocess.call(["git", "commit", "-m", "Deploy to Heroku"])

def push_to_heroku():
    """Enviar código para o Heroku"""
    print("\nEnviando código para o Heroku (isso pode levar alguns minutos)...")
    subprocess.call(["git", "push", "heroku", "master", "--force"])

def configure_heroku_app(app_name):
    """Configurar variáveis de ambiente e addons no Heroku"""
    print("\nConfigurando variáveis de ambiente...")
    subprocess.call(["heroku", "config:set", "FLASK_ENV=production", "-a", app_name])
    subprocess.call(["heroku", "config:set", "SOCKETIO_ASYNC_MODE=gevent", "-a", app_name])
    
    print("\nVerificando se o app está rodando...")
    subprocess.call(["heroku", "ps", "-a", app_name])
    
    print("\nVerificando logs...")
    subprocess.call(["heroku", "logs", "--tail", "-a", app_name])

def main():
    print("=" * 60)
    print("Assistente de Deploy do Quiz para Heroku")
    print("=" * 60)
    
    # Verificar requisitos
    if not check_heroku_cli() or not check_git():
        return
    
    # Login no Heroku
    heroku_login()
    
    # Inicializar Git e criar app no Heroku
    app_name = init_git()
    if not app_name:
        print("Não foi possível inicializar o Git ou criar o app no Heroku.")
        return
    
    # Commitar alterações
    commit_changes()
    
    # Enviar para o Heroku
    push_to_heroku()
    
    # Configurar app
    configure_heroku_app(app_name)
    
    # Abrir app no navegador
    app_url = f"https://{app_name}.herokuapp.com"
    print(f"\nSeu Quiz está disponível em: {app_url}")
    
    open_browser = input("\nDeseja abrir o app no navegador? (s/n): ").strip().lower()
    if open_browser == 's':
        webbrowser.open(app_url)
    
    print("\nDeploy concluído com sucesso!")
    print("=" * 60)

if __name__ == "__main__":
    main()
