"""
Script de inicialização específico para o Render.com
Este arquivo é executado diretamente pelo Render e configura o aplicativo
sem depender de eventlet ou gevent.
"""
import os
import sys
import logging
from app import app, socketio

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Obter a porta do ambiente (Render define a porta via variável de ambiente PORT)
    port = int(os.environ.get('PORT', 10000))
    
    # Iniciar o servidor diretamente com Flask-SocketIO
    logger.info(f"Iniciando aplicativo no modo de produção na porta {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
