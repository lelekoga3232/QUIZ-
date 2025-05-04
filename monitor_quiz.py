import os
import sys
import time
import subprocess
import signal
import psutil
import datetime
import threading
import logging
from logging.handlers import RotatingFileHandler

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('quiz_monitor.log', maxBytes=1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações
MAX_SERVER_RUNTIME = 6 * 60 * 60  # 6 horas em segundos
MEMORY_THRESHOLD = 85  # Percentual de uso de memória para reiniciar
CPU_THRESHOLD = 90  # Percentual de uso de CPU para reiniciar
CHECK_INTERVAL = 60  # Verificar a cada 60 segundos
RESTART_DELAY = 5  # Esperar 5 segundos antes de reiniciar

# Variáveis globais
server_process = None
start_time = None
monitor_running = True

def get_process_info(pid):
    """Obter informações sobre o processo"""
    try:
        process = psutil.Process(pid)
        return {
            'memory_percent': process.memory_percent(),
            'cpu_percent': process.cpu_percent(interval=1),
            'runtime': time.time() - process.create_time()
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None

def start_server():
    """Iniciar o servidor Flask/Socket.IO"""
    global server_process, start_time
    
    # Encerrar processo anterior se existir
    if server_process and server_process.poll() is None:
        try:
            os.kill(server_process.pid, signal.SIGTERM)
            logger.info(f"Processo anterior (PID: {server_process.pid}) encerrado")
            time.sleep(2)  # Dar tempo para o processo encerrar
        except:
            logger.warning("Não foi possível encerrar o processo anterior")
    
    logger.info("Iniciando servidor...")
    
    # Usar o script run_quiz_estavel.py para iniciar o servidor
    server_process = subprocess.Popen([sys.executable, 'run_quiz_estavel.py'], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
    
    start_time = time.time()
    logger.info(f"Servidor iniciado com PID: {server_process.pid}")
    
    return server_process

def should_restart(process_info):
    """Verificar se o servidor deve ser reiniciado"""
    if not process_info:
        logger.warning("Não foi possível obter informações do processo")
        return True
    
    runtime = process_info['runtime']
    memory_percent = process_info['memory_percent']
    cpu_percent = process_info['cpu_percent']
    
    # Registrar métricas
    logger.info(f"Runtime: {runtime/3600:.2f}h, Memória: {memory_percent:.1f}%, CPU: {cpu_percent:.1f}%")
    
    # Verificar condições para reinício
    if runtime > MAX_SERVER_RUNTIME:
        logger.warning(f"Tempo máximo de execução atingido: {runtime/3600:.2f} horas")
        return True
    
    if memory_percent > MEMORY_THRESHOLD:
        logger.warning(f"Uso de memória acima do limite: {memory_percent:.1f}%")
        return True
    
    if cpu_percent > CPU_THRESHOLD:
        logger.warning(f"Uso de CPU acima do limite: {cpu_percent:.1f}%")
        return True
    
    return False

def monitor_server():
    """Monitorar o servidor e reiniciar quando necessário"""
    global server_process, monitor_running
    
    while monitor_running:
        # Verificar se o processo está em execução
        if not server_process or server_process.poll() is not None:
            logger.warning("Servidor não está em execução. Reiniciando...")
            server_process = start_server()
            time.sleep(CHECK_INTERVAL)
            continue
        
        # Obter informações do processo
        process_info = get_process_info(server_process.pid)
        
        # Verificar se deve reiniciar
        if should_restart(process_info):
            logger.info("Reiniciando servidor...")
            time.sleep(RESTART_DELAY)
            server_process = start_server()
        
        # Aguardar até a próxima verificação
        time.sleep(CHECK_INTERVAL)

def handle_signal(signum, frame):
    """Manipulador de sinais para encerramento limpo"""
    global monitor_running, server_process
    
    logger.info("Sinal de encerramento recebido. Encerrando monitor...")
    monitor_running = False
    
    if server_process and server_process.poll() is None:
        try:
            os.kill(server_process.pid, signal.SIGTERM)
            logger.info(f"Processo do servidor (PID: {server_process.pid}) encerrado")
        except:
            logger.warning("Não foi possível encerrar o processo do servidor")

if __name__ == "__main__":
    # Registrar manipuladores de sinais
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info("=== Monitor de Quiz Iniciado ===")
    logger.info(f"Configurações: Runtime máximo: {MAX_SERVER_RUNTIME/3600}h, Memória: {MEMORY_THRESHOLD}%, CPU: {CPU_THRESHOLD}%")
    
    try:
        # Iniciar o servidor pela primeira vez
        server_process = start_server()
        
        # Iniciar o monitoramento
        monitor_thread = threading.Thread(target=monitor_server)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Manter o processo principal em execução
        while monitor_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro no monitor: {e}")
    finally:
        # Garantir que o processo do servidor seja encerrado
        if server_process and server_process.poll() is None:
            try:
                os.kill(server_process.pid, signal.SIGTERM)
                logger.info(f"Processo do servidor (PID: {server_process.pid}) encerrado")
            except:
                pass
        
        logger.info("=== Monitor de Quiz Encerrado ===")
