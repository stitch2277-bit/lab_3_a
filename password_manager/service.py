import os

from cryptography.fernet import Fernet, InvalidToken

from .config import database_conninfo
from .errors import ConfigurationError, DecryptionError, ValidationError
from .models import Credential, Dashboard
from .repository import PostgresRepository


TITLE_LIMIT = 120
USERNAME_LIMIT = 160
PASSWORD_LIMIT = 512


class SecretCipher:
    def __init__(self, key: str):
        try:
            self._fernet = Fernet(key)
        except ValueError as error:
            raise ConfigurationError('Укажите действительный ключ VAULT_KEY в .env.') from error

    def encrypt(self, password: str) -> bytes:
        return self._fernet.encrypt(password.encode('utf-8'))

    def decrypt(self, token: bytes) -> str:
        try:
            return self._fernet.decrypt(token).decode('utf-8')
        except (InvalidToken, UnicodeDecodeError) as error:
            raise DecryptionError('Пароль не расшифрован. Проверьте VAULT_KEY и исходные данные.') from error


class PasswordService:
    def __init__(self, repository: PostgresRepository, cipher: SecretCipher):
        self._repository = repository
        self._cipher = cipher

    @staticmethod
    def _check_text(value: str, label: str, limit: int) -> None:
        if not value:
            raise ValidationError(f'Заполните поле «{label}».')
        if len(value) > limit:
            raise ValidationError(f'Поле «{label}» допускает до {limit} символов.')
        if any(char in value for char in '\x00\r\n'):
            raise ValidationError(f'Поле «{label}» должно содержать одну строку текста.')

    def _prepare(self, title: str, username: str) -> tuple[str, str]:
        title, username = title.strip(), username.strip()
        self._check_text(title, 'Сервис', TITLE_LIMIT)
        self._check_text(username, 'Логин', USERNAME_LIMIT)
        return title, username

    def dashboard(self) -> Dashboard:
        return self._repository.dashboard()

    def get(self, entry_id: int) -> Credential:
        return self._repository.get(entry_id)

    def create(self, title: str, username: str, password: str) -> Credential:
        title, username = self._prepare(title, username)
        self._check_text(password, 'Пароль', PASSWORD_LIMIT)
        return self._repository.create(title, username, self._cipher.encrypt(password))

    def update(self, entry_id: int, title: str, username: str, password: str) -> None:
        title, username = self._prepare(title, username)
        token = None
        if password:
            self._check_text(password, 'Пароль', PASSWORD_LIMIT)
            token = self._cipher.encrypt(password)
        self._repository.update(entry_id, title, username, token)

    def delete(self, entry_id: int) -> None:
        self._repository.delete(entry_id)

    def reveal(self, entry_id: int) -> tuple[Credential, str]:
        with self._repository.reveal(entry_id) as (entry, token):
            password = self._cipher.decrypt(token)
        return entry, password


def build_service() -> PasswordService:
    repository = PostgresRepository(database_conninfo())
    cipher = SecretCipher(os.environ.get('VAULT_KEY', ''))
    return PasswordService(repository, cipher)
