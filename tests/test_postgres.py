import psycopg
import pytest
from cryptography.fernet import Fernet

from password_manager.errors import DatabaseError, DecryptionError, EntryNotFoundError
from password_manager.repository import PostgresRepository
from password_manager.service import PasswordService, SecretCipher


def test_crud_and_activity(service, database):
    title = "Почта 'личная';"
    entry = service.create(title, 'student', 'demo secret')
    assert service.dashboard().credentials == [entry]
    with psycopg.connect(database) as connection:
        token, = connection.execute('SELECT password_token FROM credentials').fetchone()
    assert b'demo secret' not in token

    service.update(entry.id, title, 'other', '')
    assert service.reveal(entry.id)[1] == 'demo secret'
    service.update(entry.id, title, 'other', 'second')
    assert service.reveal(entry.id)[1] == 'second'
    service.delete(entry.id)

    dashboard = service.dashboard()
    assert dashboard.credentials == []
    assert [event.action for event in dashboard.activity] == [
        'delete', 'reveal', 'update', 'reveal', 'update', 'create',
    ]
    assert all(event.title == title for event in dashboard.activity)
    assert len(dashboard.daily_counts) == 7
    assert sum(day.count for day in dashboard.daily_counts) == 6
    with pytest.raises(EntryNotFoundError):
        service.get(entry.id)


def test_chart_includes_empty_days_and_counts_older_events(service, database):
    with psycopg.connect(database) as connection:
        connection.execute("""
            INSERT INTO activity_log (credential_id, title, action, occurred_at)
            VALUES (1, 'A', 'create', CURRENT_TIMESTAMP - interval '6 days'),
                   (1, 'A', 'delete', CURRENT_TIMESTAMP - interval '8 days')
        """)
    dashboard = service.dashboard()
    assert len(dashboard.activity) == 2
    assert [point.count for point in dashboard.daily_counts] == [1, 0, 0, 0, 0, 0, 0]


def test_rollback_when_activity_cannot_be_written(service, database):
    with psycopg.connect(database) as connection:
        connection.execute("ALTER TABLE activity_log ADD CHECK (action <> 'create')")
    with pytest.raises(DatabaseError):
        service.create('Почта', 'student', 'demo secret')
    assert service.dashboard().credentials == []
    assert service.dashboard().activity == []


def test_failed_decryption_is_not_logged(service, database):
    entry = service.create('Почта', 'student', 'demo secret')
    different_key = SecretCipher(Fernet.generate_key().decode())
    other = PasswordService(PostgresRepository(database), different_key)
    with pytest.raises(DecryptionError):
        other.reveal(entry.id)
    assert [event.action for event in service.dashboard().activity] == ['create']
