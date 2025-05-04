import socket
import webbrowser
import os
import sys
import time
import subprocess
import signal
import threading

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

def monitor_server(process):
    """Monitorar o servidor e reiniciá-lo se cair ou se estiver com problemas"""
    consecutive_errors = 0
    max_consecutive_errors = 3
    check_interval = 5  # segundos
    health_check_url = f"http://localhost:5000/api/health"
    
    while True:
        try:
            # Verificar se o processo ainda está em execução
            if process.poll() is not None:
                print("\n[MONITOR] Servidor caiu! Reiniciando em 3 segundos...")
                time.sleep(3)
                return False  # Reiniciar o servidor
            
            # Verificar se o servidor está respondendo (health check)
            try:
                # Tentar fazer uma requisição para verificar se o servidor está respondendo
                response = None
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)  # timeout de 2 segundos
                    result = s.connect_ex(('localhost', 5000))
                    if result == 0:
                        # Porta está aberta, servidor está respondendo
                        consecutive_errors = 0
                    else:
                        # Porta não está aberta, servidor não está respondendo
                        consecutive_errors += 1
                        print(f"[MONITOR] Aviso: Servidor não está respondendo (erro {consecutive_errors}/{max_consecutive_errors})")
            except Exception as e:
                consecutive_errors += 1
                print(f"[MONITOR] Erro ao verificar saúde do servidor: {e} (erro {consecutive_errors}/{max_consecutive_errors})")
            
            # Se houver muitos erros consecutivos, reiniciar o servidor
            if consecutive_errors >= max_consecutive_errors:
                print("\n[MONITOR] Servidor não está respondendo após várias tentativas. Reiniciando...")
                try:
                    # Tentar encerrar o processo de forma limpa
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    # Se não conseguir encerrar de forma limpa, forçar encerramento
                    try:
                        process.kill()
                    except:
                        pass
                return False  # Reiniciar o servidor
        except Exception as e:
            print(f"[MONITOR] Erro no monitoramento: {e}")
        
        # Verificar a cada X segundos
        time.sleep(check_interval)

def run_quiz_estavel():
    """Executar o quiz com configurações para estabilidade"""
    # Obter endereço IP local
    local_ip = get_local_ip()
    
    # Porta padrão
    port = 5000
    
    # Imprimir informações de acesso
    print("\n" + "="*60)
    print(f"Quiz Application - Versão Ultra Estável")
    print("="*60)
    print(f"URL Local:     http://localhost:{port}")
    print(f"URL da Rede:   http://{local_ip}:{port}")
    print("\nCompartilhe a URL da Rede com outros dispositivos na sua rede local")
    print("para acessar seu quiz de outros dispositivos.")
    print("\nPressione Ctrl+C para parar o servidor")
    print("="*60 + "\n")
    
    # Abrir navegador com a URL local
    webbrowser.open(f"http://localhost:{port}")
    
    # Configurar variáveis de ambiente para Flask
    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["FLASK_ENV"] = "production"  # Usar modo de produção para maior estabilidade
    
    # Configurações para Socket.IO
    env["SOCKETIO_PING_TIMEOUT"] = "120"
    env["SOCKETIO_PING_INTERVAL"] = "10"
    
    # Loop para manter o servidor rodando
    while True:
        try:
            print("[INFO] Iniciando servidor Flask...")
            
            # Iniciar o servidor Flask como um processo separado
            process = subprocess.Popen(
                ["python", "app.py"],
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Iniciar thread para monitorar o servidor
            monitor_thread = threading.Thread(target=monitor_server, args=(process,))
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Aguardar o processo terminar
            process.wait()
            
            # Se chegou aqui, o processo terminou
            print("[INFO] Servidor encerrado.")
            
            # Verificar se foi uma saída intencional
            if hasattr(process, 'was_killed') and process.was_killed:
                break
            
            # Caso contrário, reiniciar o servidor
            print("[INFO] Reiniciando servidor em 3 segundos...")
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n[INFO] Encerrando servidor por solicitação do usuário...")
            
            # Marcar que o processo foi encerrado intencionalmente
            if 'process' in locals():
                process.was_killed = True
                
                # Tentar encerrar o processo de forma limpa
                try:
                    if sys.platform == 'win32':
                        process.send_signal(signal.CTRL_C_EVENT)
                    else:
                        process.send_signal(signal.SIGINT)
                    
                    # Dar um tempo para o processo encerrar
                    for _ in range(5):
                        if process.poll() is not None:
                            break
                        time.sleep(1)
                    
                    # Se ainda estiver rodando, forçar encerramento
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                except:
                    # Em caso de erro, tentar encerrar de forma forçada
                    try:
                        process.kill()
                    except:
                        pass
            
            break
        except Exception as e:
            print(f"\n[ERRO] Ocorreu um erro: {e}")
            print("[INFO] Reiniciando servidor em 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    run_quiz_estavel()
