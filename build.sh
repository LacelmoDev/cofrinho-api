#!/usr/bin/env bash
# Comando de build no Render
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
