# Менеджер паролей

Лабораторная работа № 3 по Python. Вариант 9, уровень Well-done.

Десктопное приложение на PySide6 и веб-версия на FastAPI работают с одной базой PostgreSQL. В обеих версиях доступны таблица записей, добавление, изменение, просмотр пароля, удаление, журнал и график активности за семь дней. Название сервиса и логин видны в таблице. Пароль открывается отдельным действием.

## Запуск на Windows

Понадобятся Python 3.12 и запущенный Docker Desktop. Откройте PowerShell в папке репозитория.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m password_manager.setup
docker compose up -d --wait db
```

Команда настройки создаёт `.env` со случайным паролем PostgreSQL и ключом Fernet при первом запуске. Сохраните этот файл для последующих запусков. Обе версии должны использовать один и тот же ключ. `.env` исключён из Git.

Запустите веб-сервер в первом окне PowerShell и откройте [веб-версию](http://127.0.0.1:8000).

```powershell
.\.venv\Scripts\python.exe -m password_manager.web
```

Во втором окне PowerShell запустите десктоп.

```powershell
.\.venv\Scripts\python.exe -m password_manager.desktop
```

Кнопка «Обновить» показывает изменения из другого интерфейса. «Файл → Выход» закрывает десктопное окно или открывает страницу завершения работы в браузере. Веб-сервер останавливается клавишами Ctrl+C в его терминале. Обычная команда `docker compose down` останавливает контейнер и сохраняет данные в томе `postgres_data`.

## Параметры для DBeaver

| Поле | Значение по умолчанию |
| --- | --- |
| Драйвер | PostgreSQL |
| Host | `127.0.0.1` |
| Port | `5433` на компьютере, `5432` внутри контейнера |
| Database | `password_manager` |
| Username | `lab_user` |
| Password | значение `POSTGRES_PASSWORD` из `.env` |

Для просмотра откройте `public.credentials` и `public.activity_log`. В колонке `password_token` хранится двоичный токен Fernet. Если порт 5433 занят, измените `DB_PORT` в `.env` и повторите `docker compose up -d --wait db`. Подключение вводится вручную в DBeaver. [Поля подключения PostgreSQL в DBeaver](https://dbeaver.com/docs/dbeaver/Database-driver-PostgreSQL/)

## Тесты

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -v
Remove-Item Env:RUN_DB_TESTS
```

Первый запуск выполняет модульные тесты. Второй добавляет PostgreSQL и проверку обмена данными между FastAPI и реальными виджетами PySide6. Для каждого интеграционного теста создаётся временная схема в том же контейнере. Рабочие таблицы находятся в схеме `public`.

## Устройство проекта

- [desktop.py](password_manager/desktop.py) — окно и формы PySide6.
- [web.py](password_manager/web.py) и [templates](password_manager/templates) — маршруты FastAPI и шаблоны HTML.
- [service.py](password_manager/service.py) — правила ввода, операции и шифрование.
- [repository.py](password_manager/repository.py) — запросы через Psycopg и транзакции.
- [schema.sql](db/schema.sql) — таблицы, ограничения, индекс журнала.
- [DEFENSE.md](DEFENSE.md) — ответы и последовательность показа на защите.
- [Лабораторная работа 3.docx](docs/Лабораторная%20работа%203.docx) — отчёт.

Это локальный однопользовательский MVP. Сервер привязан к `127.0.0.1`, отдельной авторизации в приложении нет. Для демонстрации подходят вымышленные учётные данные.
