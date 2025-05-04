import socket
import webbrowser
import os
import sys
import time
import subprocess

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

def run_quiz_corrigido():
    """Executar o quiz com correções para o Socket.IO"""
    # Obter endereço IP local
    local_ip = get_local_ip()
    
    # Porta padrão
    port = 5000
    
    # Imprimir informações de acesso
    print("\n" + "="*60)
    print(f"Quiz Application - Versão Corrigida")
    print("="*60)
    print(f"URL Local:     http://localhost:{port}")
    print(f"URL da Rede:   http://{local_ip}:{port}")
    print("\nCompartilhe a URL da Rede com outros dispositivos na sua rede local")
    print("para acessar seu quiz de outros dispositivos.")
    print("\nPressione Ctrl+C para parar o servidor")
    print("="*60 + "\n")
    
    # Abrir navegador com a URL local
    webbrowser.open(f"http://localhost:{port}")
    
    # Executar o Flask app diretamente
    os.system(f"python app.py")

if __name__ == "__main__":
    run_quiz_corrigido()
