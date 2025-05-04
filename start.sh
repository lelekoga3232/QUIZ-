#!/bin/bash
# Script para iniciar o aplicativo no Render

echo "Iniciando aplicativo com Gunicorn (modo padrão)..."
gunicorn --workers 3 --timeout 120 app:app
