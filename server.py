"""
Script principal para executar o servidor no Render.com
Este arquivo é o ponto de entrada principal para o Render.
"""
import os
import sys
import logging
from app import app, socketio

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ponto de entrada principal
if __name__ == "__main__":
    # Obter a porta do ambiente (Render define a porta via variável de ambiente PORT)
    port = int(os.environ.get('PORT', 10000))
    
    # Iniciar o servidor diretamente com Flask-SocketIO
    logger.info(f"Iniciando servidor na porta {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
