from unittest.mock import Mock

import psycopg
import pytest
from cryptography.fernet import Fernet

from password_manager.errors import ConfigurationError, DatabaseError, DecryptionError, ValidationError
from password_manager.repository import PostgresRepository
from password_manager.service import PasswordService, SecretCipher


@pytest.fixture
def cipher():
    return SecretCipher(Fernet.generate_key().decode())


def test_encryption_round_trip(cipher):
    text = '  Учебный&пароль42  '
    first, second = cipher.encrypt(text), cipher.encrypt(text)
    assert first != second
    assert text.encode() not in first
    assert cipher.decrypt(first) == text


def test_wrong_key_and_invalid_token(cipher):
    other = SecretCipher(Fernet.generate_key().decode())
    for token in (other.encrypt('test'), b'broken'):
        with pytest.raises(DecryptionError, match='Пароль не расшифрован'):
            cipher.decrypt(token)


def test_invalid_key():
    with pytest.raises(ConfigurationError):
        SecretCipher('invalid')


@pytest.mark.parametrize('title,username,password,field', [
    ('  ', 'login', 'secret', 'Сервис'),
    ('Сервис', '', 'secret', 'Логин'),
    ('Сервис', 'login', '', 'Пароль'),
    ('x' * 121, 'login', 'secret', 'Сервис'),
    ('Сервис', 'x' * 161, 'secret', 'Логин'),
    ('Сервис', 'login', 'x' * 513, 'Пароль'),
    ('Сервис', 'bad\x00login', 'secret', 'Логин'),
], ids=['blank-title', 'blank-login', 'empty-password', 'long-title',
       'long-login', 'long-password', 'null-byte'])
def test_create_rejects_bad_fields(cipher, title, username, password, field):
    repository = Mock(spec=PostgresRepository)
    with pytest.raises(ValidationError, match=field):
        PasswordService(repository, cipher).create(title, username, password)
    repository.create.assert_not_called()


def test_service_passes_encrypted_secret_and_normalized_labels(cipher):
    repository = Mock(spec=PostgresRepository)
    service = PasswordService(repository, cipher)
    service.create('  Почта  ', '  student ', ' demo secret ')
    title, username, token = repository.create.call_args.args
    assert (title, username) == ('Почта', 'student')
    assert cipher.decrypt(token) == ' demo secret '


def test_empty_edit_password_means_keep_existing(cipher):
    repository = Mock(spec=PostgresRepository)
    PasswordService(repository, cipher).update(42, 'Почта', 'student', '')
    repository.update.assert_called_once_with(42, 'Почта', 'student', None)


def test_connection_failure_has_user_facing_message(monkeypatch):
    def offline(*args, **kwargs):
        raise psycopg.OperationalError('private connection details')

    monkeypatch.setattr(psycopg, 'connect', offline)
    with pytest.raises(DatabaseError, match='Связь с PostgreSQL') as error:
        PostgresRepository('dbname=sample').dashboard()
    assert 'private' not in str(error.value)
