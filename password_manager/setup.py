from secrets import token_hex

from cryptography.fernet import Fernet

from .config import ROOT


def main() -> None:
    settings = (ROOT / '.env.example').read_text(encoding='utf-8')
    settings = settings.replace('POSTGRES_PASSWORD=\n', f'POSTGRES_PASSWORD={token_hex(24)}\n')
    key = Fernet.generate_key().decode('ascii')
    settings = settings.replace('VAULT_KEY=\n', f'VAULT_KEY={key}\n')
    try:
        with (ROOT / '.env').open('x', encoding='utf-8') as file:
            file.write(settings)
    except FileExistsError:
        print('.env уже существует. Приложение использует сохранённые параметры.')
        return
    print('Файл .env создан.')


if __name__ == '__main__':
    main()
