import os
import sys
import subprocess
import time
import socket
import webbrowser
import logging
import threading
import signal
import atexit

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
PORT = 5000
WORKERS = 4  # Número de workers concorrentes

def get_local_ip():
    """Obter o endereço IP local da máquina"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return socket.gethostbyname(socket.gethostname())

def check_port_available(port):
    """Verificar se a porta está disponível"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def kill_process_on_port(port):
    """Matar processo que está usando a porta especificada"""
    try:
        if sys.platform == 'win32':
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            if output:
                for line in output.splitlines():
                    if 'LISTENING' in line:
                        pid = line.split()[-1]
                        subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                        logger.info(f"Processo com PID {pid} na porta {port} encerrado")
        else:
            output = subprocess.check_output(f'lsof -i :{port} -t', shell=True).decode()
            if output:
                pid = output.strip()
                subprocess.call(f'kill -9 {pid}', shell=True)
                logger.info(f"Processo com PID {pid} na porta {port} encerrado")
    except Exception as e:
        logger.warning(f"Erro ao tentar matar processo na porta {port}: {e}")

def install_requirements():
    """Instalar dependências necessárias"""
    try:
        logger.info("Verificando dependências...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gunicorn", "gevent"])
        logger.info("Dependências instaladas com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro ao instalar dependências: {e}")
        return False

def run_gunicorn_server():
    """Executar servidor gunicorn"""
    # Verificar se a porta está em uso
    if not check_port_available(PORT):
        logger.warning(f"A porta {PORT} já está em uso. Tentando matar o processo existente...")
        kill_process_on_port(PORT)
        time.sleep(2)
    
    # Preparar comando gunicorn
    if sys.platform == 'win32':
        # Windows não suporta gunicorn nativamente, então usamos o waitress
        cmd = [
            sys.executable, "-m", "waitress", 
            f"--port={PORT}", 
            f"--host=0.0.0.0",
            "app:app"
        ]
    else:
        # Linux/Mac usam gunicorn
        cmd = [
            "gunicorn",
            f"--workers={WORKERS}",
            "--worker-class=gevent",
            f"--bind=0.0.0.0:{PORT}",
            "--timeout=120",
            "--keep-alive=5",
            "--access-logfile=-",
            "--error-logfile=-",
            "--log-level=info",
            "app:app"
        ]
    
    # Variáveis de ambiente
    env = os.environ.copy()
    env["QUIZ_MODE"] = "production"
    env["SOCKETIO_ASYNC_MODE"] = "gevent"
    env["PYTHONUNBUFFERED"] = "1"
    
    # Iniciar o servidor
    logger.info(f"Iniciando servidor em modo produção na porta {PORT}...")
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Registrar o processo para limpeza na saída
    atexit.register(lambda: process.terminate() if process.poll() is None else None)
    
    # Thread para ler e imprimir a saída
    def output_reader():
        for line in iter(process.stdout.readline, ''):
            if line:
                logger.info(f"Server: {line.rstrip()}")
    
    # Iniciar thread para ler a saída
    output_thread = threading.Thread(target=output_reader)
    output_thread.daemon = True
    output_thread.start()
    
    return process

def monitor_server(process):
    """Monitorar o servidor e reiniciá-lo se necessário"""
    last_restart = time.time()
    consecutive_failures = 0
    
    while True:
        try:
            # Verificar se o processo ainda está rodando
            if process.poll() is not None:
                logger.warning(f"Servidor encerrado com código {process.returncode}")
                consecutive_failures += 1
                
                # Evitar reiniciar muito frequentemente
                current_time = time.time()
                if current_time - last_restart < 10:  # No mínimo 10 segundos entre reinícios
                    wait_time = 10 - (current_time - last_restart)
                    logger.info(f"Aguardando {wait_time:.1f}s antes de reiniciar...")
                    time.sleep(wait_time)
                
                # Reiniciar servidor
                logger.info("Reiniciando servidor...")
                process = run_gunicorn_server()
                last_restart = time.time()
            else:
                # Verificar se o servidor está respondendo
                if check_server_health():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.warning(f"Servidor não está respondendo (falha {consecutive_failures}/3)")
                    
                    # Se houver muitas falhas consecutivas, reiniciar
                    if consecutive_failures >= 3:
                        logger.warning("Servidor não responde após múltiplas tentativas. Reiniciando...")
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                        
                        # Aguardar um pouco
                        time.sleep(2)
                        
                        # Reiniciar servidor
                        process = run_gunicorn_server()
                        last_restart = time.time()
                        consecutive_failures = 0
        
        except Exception as e:
            logger.error(f"Erro no monitoramento: {e}")
        
        # Verificar a cada 10 segundos
        time.sleep(10)

def check_server_health():
    """Verificar se o servidor está respondendo"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            result = s.connect_ex(('localhost', PORT))
            return result == 0
    except:
        return False

def run_quiz_production():
    """Executar o quiz em modo de produção"""
    logger.info("=== Modo de Produção do Quiz - Para execução 24/7 ===")
    
    # Obter IP local para exibir URL de acesso
    local_ip = get_local_ip()
    
    # Instalar dependências necessárias
    if not install_requirements():
        logger.error("Falha ao instalar dependências. Tentando continuar mesmo assim...")
    
    # Exibir informações de acesso
    print("\n" + "="*60)
    print(f"Quiz Application - Modo Produção 24/7")
    print("="*60)
    print(f"URL Local:     http://localhost:{PORT}")
    print(f"URL da Rede:   http://{local_ip}:{PORT}")
    print("\nCompartilhe a URL da Rede com outros dispositivos na sua rede local")
    print("para acessar seu quiz de outros dispositivos.")
    print("\nPressione Ctrl+C para parar o servidor")
    print("="*60 + "\n")
    
    # Iniciar servidor
    server_process = run_gunicorn_server()
    
    # Abrir navegador
    time.sleep(2)  # Dar tempo para o servidor iniciar
    webbrowser.open(f"http://localhost:{PORT}")
    
    try:
        # Iniciar monitoramento em thread separada
        monitor_thread = threading.Thread(target=monitor_server, args=(server_process,))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Manter o processo principal rodando
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
    finally:
        # Tentar encerrar o processo do servidor se ainda estiver rodando
        if server_process and server_process.poll() is None:
            logger.info("Encerrando servidor...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except:
                server_process.kill()

if __name__ == "__main__":
    run_quiz_production()
