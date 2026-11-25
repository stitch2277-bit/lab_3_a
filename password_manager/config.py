import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

from .errors import ConfigurationError


ROOT = Path(__file__).resolve().parent.parent


def database_conninfo() -> str:
    load_dotenv(ROOT / '.env')
    password = os.environ.get('POSTGRES_PASSWORD')
    if not password:
        raise ConfigurationError('Выполните python -m password_manager.setup для настройки .env.')
    try:
        port = int(os.environ.get('DB_PORT', '5433'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as error:
        raise ConfigurationError('DB_PORT должен быть числом от 1 до 65535.') from error

    return make_conninfo(
        host=os.environ.get('DB_HOST', '127.0.0.1'),
        port=port,
        dbname=os.environ.get('POSTGRES_DB', 'password_manager'),
        user=os.environ.get('POSTGRES_USER', 'lab_user'),
        password=password,
        connect_timeout=3,
        options='-c statement_timeout=5000 -c TimeZone=UTC',
    )
