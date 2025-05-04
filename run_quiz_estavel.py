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

def run_quiz_estavel():
    """Executar o quiz com configurações otimizadas para estabilidade de conexão"""
    # Obter endereço IP local
    local_ip = get_local_ip()
    
    # Porta padrão
    port = 5000
    
    # Analisar argumentos da linha de comando para porta personalizada
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Número de porta inválido: {sys.argv[1]}. Usando porta padrão {port}.")
    
    # Imprimir informações de acesso
    print("\n" + "="*60)
    print(f"Quiz Application - Acesso Estável pela Rede")
    print("="*60)
    print(f"URL Local:     http://localhost:{port}")
    print(f"URL da Rede:   http://{local_ip}:{port}")
    print("\nCompartilhe a URL da Rede com outros dispositivos na sua rede local")
    print("para acessar seu quiz de outros dispositivos.")
    print("\nPressione Ctrl+C para parar o servidor")
    print("="*60 + "\n")
    
    # Configurar variáveis de ambiente para Flask e Socket.IO
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Configurações específicas para Socket.IO
    os.environ['SOCKETIO_CORS_ALLOWED_ORIGINS'] = '*'
    os.environ['SOCKETIO_ASYNC_MODE'] = 'threading'
    os.environ['SOCKETIO_PING_TIMEOUT'] = '120'
    os.environ['SOCKETIO_PING_INTERVAL'] = '10'
    os.environ['SOCKETIO_MAX_HTTP_BUFFER_SIZE'] = '5242880'  # 5MB
    os.environ['SOCKETIO_ALWAYS_CONNECT'] = 'true'
    os.environ['SOCKETIO_ENGINEIO_LOGGER'] = 'true'
    os.environ['SOCKETIO_LOGGER'] = 'true'
    
    # Abrir navegador com a URL local
    webbrowser.open(f"http://localhost:{port}")
    
    # Comando para executar o Flask com configurações otimizadas
    cmd = f"""
    python -c "
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from app import app, socketio

if __name__ == '__main__':
    print('Iniciando servidor com configurações otimizadas para Socket.IO...')
    socketio.run(
        app, 
        host='0.0.0.0', 
        port={port}, 
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
"
    """
    
    # Executar o comando
    os.system(cmd)

if __name__ == "__main__":
    run_quiz_estavel()
