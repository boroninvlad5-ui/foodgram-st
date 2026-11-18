# Фудграм

Веб-приложение для публикации рецептов. Пользователи могут подписываться на
авторов, сохранять рецепты в избранное и собирать список покупок. Бэкенд
реализован на Django REST Framework по спецификации `docs/openapi-schema.yml`.

## Локальный запуск на macOS

Для повторного запуска откройте `start_local.command` двойным щелчком и
перейдите на <http://127.0.0.1:8000/>. Окно терминала должно оставаться открытым.

Если macOS не разрешает открыть `.command` двойным щелчком, выполните в
терминале из корня проекта:

```sh
./start_local.command
```

API-спецификация: <http://127.0.0.1:8000/api/docs/>.
Админка: <http://127.0.0.1:8000/admin/>.

Для подготовки проекта с нуля:

```sh
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python manage.py migrate
venv/bin/python manage.py load_ingredients
venv/bin/python manage.py seed_demo
```

Команда `seed_demo` выводит случайный пароль трёх демонстрационных аккаунтов.
Демонстрационные данные не обязательны для работы приложения. Для сборки
интерфейса с нуля установите Node.js, затем выполните в `frontend`
`npm install --legacy-peer-deps` и `npm run build`.

## Структура

- `backend` — Django, REST API, модели, админка и команды загрузки данных.
- `frontend` — готовый React-интерфейс.
- `data` — список ингредиентов.
- `docs` — спецификация API.
- `postman_collection` — запросы для ручной проверки.

В локальном режиме используется SQLite. Настройки бэкенда поддерживают
PostgreSQL через переменные окружения `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST` и `POSTGRES_PORT`.

## Контейнерный запуск

При наличии Docker Compose выполните из папки `infra`:

```sh
docker compose up --build
```

Контейнер `frontend` собирает файлы интерфейса и завершается. Постоянно
работают `nginx`, `backend` и `db`. Данные PostgreSQL, медиафайлы и сборка
интерфейса сохраняются в Docker volumes. Перед публикацией задайте в
окружении сильный `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY` и нужные адреса в
`DJANGO_ALLOWED_HOSTS`.

GitHub Actions запускает проверку стиля и тесты, а также собирает образ
бэкенда. Для публикации образа в Docker Hub настройте секреты репозитория
`DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN`.

