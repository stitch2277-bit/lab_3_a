from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from .errors import DatabaseError, EntryNotFoundError
from .models import Action, Activity, Credential, DailyCount, Dashboard


class PostgresRepository:
    def __init__(self, conninfo: str):
        self._conninfo = conninfo

    @contextmanager
    def _transaction(self) -> Iterator[psycopg.Connection]:
        try:
            with psycopg.connect(self._conninfo, row_factory=dict_row) as connection:
                yield connection
        except psycopg.OperationalError as error:
            raise DatabaseError('Связь с PostgreSQL прервана. Проверьте контейнер и настройки .env.') from error
        except psycopg.Error as error:
            raise DatabaseError('Ошибка запроса к PostgreSQL. Проверьте состояние схемы базы.') from error

    @staticmethod
    def _log(connection: psycopg.Connection, entry: Credential, action: Action) -> None:
        connection.execute(
            'INSERT INTO activity_log (credential_id, title, action) VALUES (%s, %s, %s)',
            (entry.id, entry.title, action),
        )

    @staticmethod
    def _entry(row: dict | None) -> Credential:
        if row is None:
            raise EntryNotFoundError('Запись не найдена. Обновите список.')
        return Credential(row['id'], row['title'], row['username'])

    def dashboard(self) -> Dashboard:
        today = datetime.now(UTC).date()
        first_day = today - timedelta(days=6)
        with self._transaction() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            entries = connection.execute(
                'SELECT id, title, username FROM credentials ORDER BY id DESC'
            ).fetchall()
            activity = connection.execute('''
                SELECT title, action, occurred_at FROM activity_log
                ORDER BY occurred_at DESC, id DESC LIMIT 20
            ''').fetchall()
            totals = connection.execute('''
                SELECT (occurred_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS count
                FROM activity_log
                WHERE occurred_at >= (%s::date::timestamp AT TIME ZONE 'UTC')
                  AND occurred_at < (%s::date::timestamp AT TIME ZONE 'UTC')
                GROUP BY day
            ''', (first_day, today + timedelta(days=1))).fetchall()
        counts = {row['day']: row['count'] for row in totals}
        days = [first_day + timedelta(days=offset) for offset in range(7)]
        return Dashboard(
            [self._entry(row) for row in entries],
            [Activity(**row) for row in activity],
            [DailyCount(day, counts.get(day, 0)) for day in days],
        )

    def get(self, entry_id: int) -> Credential:
        with self._transaction() as connection:
            row = connection.execute(
                'SELECT id, title, username FROM credentials WHERE id = %s', (entry_id,),
            ).fetchone()
            return self._entry(row)

    def create(self, title: str, username: str, token: bytes) -> Credential:
        with self._transaction() as connection:
            row = connection.execute('''
                INSERT INTO credentials (title, username, password_token) VALUES (%s, %s, %s)
                RETURNING id, title, username
            ''', (title, username, token)).fetchone()
            entry = self._entry(row)
            self._log(connection, entry, 'create')
            return entry

    def update(self, entry_id: int, title: str, username: str, token: bytes | None) -> None:
        with self._transaction() as connection:
            row = connection.execute('''
                UPDATE credentials SET title = %s, username = %s,
                    password_token = COALESCE(%s, password_token)
                WHERE id = %s RETURNING id, title, username
            ''', (title, username, token, entry_id)).fetchone()
            self._log(connection, self._entry(row), 'update')

    def delete(self, entry_id: int) -> None:
        with self._transaction() as connection:
            row = connection.execute('''
                DELETE FROM credentials WHERE id = %s RETURNING id, title, username
            ''', (entry_id,)).fetchone()
            self._log(connection, self._entry(row), 'delete')

    @contextmanager
    def reveal(self, entry_id: int) -> Iterator[tuple[Credential, bytes]]:
        with self._transaction() as connection:
            row = connection.execute('''
                SELECT id, title, username, password_token FROM credentials WHERE id = %s
            ''', (entry_id,)).fetchone()
            entry = self._entry(row)
            yield entry, row['password_token']
            self._log(connection, entry, 'reveal')
