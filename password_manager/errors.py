class VaultError(Exception):
    """Ожидаемая ошибка, текст которой можно показать пользователю."""


class ValidationError(VaultError):
    """Поля не прошли проверку."""


class EntryNotFoundError(VaultError):
    """Запись с таким ID отсутствует."""


class DatabaseError(VaultError):
    """Запрос к хранилищу не выполнен."""


class ConfigurationError(VaultError):
    """Параметры запуска отсутствуют или неверны."""


class DecryptionError(VaultError):
    """Сохранённый пароль невозможно расшифровать."""
