#!/bin/bash
# Script para iniciar o aplicativo no Render

echo "Iniciando aplicativo com Gunicorn + Eventlet..."
gunicorn --worker-class eventlet --workers 1 app:app
