# Backend Sufler

Django backend приложения: веб-интерфейс, модели чатов и административная часть.
ASR-сервис размещен рядом как отдельная точка запуска.

## Структура monorepo

```text
sufler/
├── backend/                         # каноническая точка сборки
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── sufler/                      # Django project
│   │   ├── __init__.py
│   │   ├── celery.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── chat/                        # Django app
│   │   ├── migrations/
│   │   └── ...
│   ├── services/
│   │   └── asr/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       └── requirements.txt
│   ├── templates/
│   ├── static/
│   └── staticfiles/
├── infra/                           # Docker Compose и env-шаблон
├── tests/
│   └── acceptance/
│       └── test_smoke.py
├── dashboard/app/                   # legacy Django wrappers
├── recognizer/main.py               # legacy ASR wrapper
├── docs/                            # source of truth для ТЗ
└── canvases/                        # source of truth для UI
```

## Запуск в Windows PowerShell

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py runserver
```

Smoke test из `backend/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover ..\tests\acceptance -v
```

Минимальные команды для CI из `backend/`:

```powershell
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate --noinput
python -m unittest discover ..\tests\acceptance -v
```

## ASR

Модель ищется в `services/asr/model/vosk-model-ru-0.22`, затем в старом
`../recognizer/model/vosk-model-ru-0.22`. Путь можно задать через
`$env:VOSK_MODEL_PATH`. Сервер сохраняет адрес `ws://localhost:8765`.

```powershell
$asrPython = ".\.venv\Scripts\python.exe"
& $asrPython -m pip install -r services\asr\requirements.txt
$env:VOSK_MODEL_PATH = "C:\models\vosk-model-ru-0.22"
& $asrPython -m services.asr.main
```

## Legacy-команды

Старые точки входа остаются рабочими:

```powershell
cd dashboard\app
.\.venv\Scripts\python.exe manage.py runserver
cd ..\..\recognizer
..\backend\.venv\Scripts\python.exe main.py
```

Импорты `app.settings`, `app.urls`, `app.wsgi` и `app.asgi` поддерживаются
совместимыми shim-модулями.
