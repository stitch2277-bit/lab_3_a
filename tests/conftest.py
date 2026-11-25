import os
from uuid import uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from password_manager.config import ROOT, database_conninfo
from password_manager.repository import PostgresRepository
from password_manager.service import PasswordService, SecretCipher


@pytest.fixture
def database():
    if os.environ.get('RUN_DB_TESTS') != '1':
        pytest.skip('Запустите PostgreSQL и задайте RUN_DB_TESTS=1 для интеграционных тестов.')

    conninfo = database_conninfo()
    schema_name = f'lab_test_{uuid4().hex}'
    schema = sql.Identifier(schema_name)
    with psycopg.connect(conninfo, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(schema))
        try:
            options = conninfo_to_dict(conninfo)['options']
            test_conninfo = make_conninfo(conninfo, options=f'{options} -c search_path={schema_name}')
            with psycopg.connect(test_conninfo) as connection:
                connection.execute((ROOT / 'db/schema.sql').read_text(encoding='utf-8'))
            yield test_conninfo
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(schema))


@pytest.fixture
def service(database):
    return PasswordService(PostgresRepository(database), SecretCipher(Fernet.generate_key().decode()))
