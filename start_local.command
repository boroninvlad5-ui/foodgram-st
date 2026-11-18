#!/bin/zsh
set -e

cd "$(dirname "$0")/backend"

if curl --silent --fail http://127.0.0.1:8000/api/recipes/ >/dev/null; then
  open "http://127.0.0.1:8000/"
  echo "Фудграм уже работает."
  exit 0
fi

if [[ ! -x venv/bin/python ]]; then
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
fi

venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py load_ingredients

if [[ ! -f ../frontend/build/index.html ]]; then
  echo "Сначала соберите интерфейс: cd frontend && npm install && npm run build"
  exit 1
fi

echo "Фудграм: http://127.0.0.1:8000/"
echo "Остановить сервер: Ctrl+C"
open "http://127.0.0.1:8000/"
venv/bin/python manage.py runserver 127.0.0.1:8000
