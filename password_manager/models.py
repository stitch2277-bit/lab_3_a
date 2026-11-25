from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


Action = Literal['create', 'update', 'reveal', 'delete']
ACTION_LABELS = {
    'create': 'Добавление',
    'update': 'Изменение',
    'reveal': 'Просмотр пароля',
    'delete': 'Удаление',
}


@dataclass(frozen=True)
class Credential:
    id: int
    title: str
    username: str


@dataclass(frozen=True)
class Activity:
    title: str
    action: Action
    occurred_at: datetime

    @property
    def label(self) -> str:
        return ACTION_LABELS[self.action]


@dataclass(frozen=True)
class DailyCount:
    day: date
    count: int


@dataclass(frozen=True)
class Dashboard:
    credentials: list[Credential]
    activity: list[Activity]
    daily_counts: list[DailyCount]
