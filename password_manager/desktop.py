import sys
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .errors import VaultError
from .models import Activity, Credential, DailyCount
from .service import PASSWORD_LIMIT, TITLE_LIMIT, USERNAME_LIMIT, PasswordService, build_service


def plain_label(text: str = '') -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class EntryDialog(QDialog):
    def __init__(self, service: PasswordService, entry: Credential | None, parent: QWidget):
        super().__init__(parent)
        self._service = service
        self._entry = entry
        self.setWindowTitle('Изменить запись' if entry else 'Добавить запись')
        self.setMinimumWidth(390)

        self.title_input = QLineEdit(entry.title if entry else '')
        self.title_input.setMaxLength(TITLE_LIMIT)
        self.username_input = QLineEdit(entry.username if entry else '')
        self.username_input.setMaxLength(USERNAME_LIMIT)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMaxLength(PASSWORD_LIMIT)
        self.error_label = plain_label()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet('color: #a0272b;')
        self.error_label.hide()

        form = QFormLayout()
        form.addRow('Сервис', self.title_input)
        form.addRow('Логин', self.username_input)
        form.addRow('Пароль', self.password_input)

        save = QPushButton('Сохранить')
        cancel = QPushButton('Отмена')
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(cancel)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        if entry:
            hint = plain_label('Оставьте поле пустым, чтобы сохранить прежний пароль.')
            hint.setWordWrap(True)
            layout.addWidget(hint)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)
        self.title_input.setFocus()

    def _save(self) -> None:
        title = self.title_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        try:
            if self._entry is None:
                self._service.create(title, username, password)
            else:
                self._service.update(self._entry.id, title, username, password)
        except VaultError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        self.password_input.clear()
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, service: PasswordService):
        super().__init__()
        self._service = service
        self.setWindowTitle('Менеджер паролей')
        self.resize(940, 580)
        self.setMinimumSize(660, 550)

        file_menu = self.menuBar().addMenu('Файл')
        file_menu.addAction('Обновить', self.refresh, 'F5')
        file_menu.addSeparator()
        file_menu.addAction('Выход', self.close, 'Ctrl+Q')

        add_button = QPushButton('Добавить запись')
        add_button.clicked.connect(self.add_entry)
        refresh_button = QPushButton('Обновить')
        refresh_button.clicked.connect(self.refresh)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Сервис', 'Логин', 'Действия'])
        self.table.setAccessibleName('Таблица записей')
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.empty_label = plain_label('Записей пока нет.')
        entries_group = QGroupBox('Записи')
        entries_layout = QVBoxLayout(entries_group)
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        toolbar.addWidget(refresh_button)
        toolbar.addWidget(add_button)
        entries_layout.addLayout(toolbar)
        entries_layout.addWidget(self.table, 1)
        entries_layout.addWidget(self.empty_label)

        chart_group = QGroupBox('Активность за 7 дней')
        chart_group.setStyleSheet(
            'QProgressBar { background: #e7ecf2; border: none; border-radius: 4px; }'
            'QProgressBar::chunk { background: #2256a5; border-radius: 4px; }'
        )
        chart_layout = QVBoxLayout(chart_group)
        chart_layout.addWidget(plain_label('Количество действий по дням, UTC'))
        self.chart_rows: list[tuple[QLabel, QProgressBar, QLabel]] = []
        for _ in range(7):
            date_label, count_label = plain_label(), plain_label()
            date_label.setMinimumWidth(44)
            count_label.setMinimumWidth(30)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            row = QHBoxLayout()
            row.addWidget(date_label)
            row.addWidget(bar, 1)
            row.addWidget(count_label)
            chart_layout.addLayout(row)
            self.chart_rows.append((date_label, bar, count_label))
        chart_layout.addStretch()

        journal_group = QGroupBox('Журнал активности')
        self.journal = QListWidget()
        self.journal.setAccessibleName('Последние действия')
        self.journal.setWordWrap(True)
        QVBoxLayout(journal_group).addWidget(self.journal)

        overview = QHBoxLayout()
        overview.addWidget(chart_group, 4)
        overview.addWidget(journal_group, 5)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(entries_group, 3)
        layout.addLayout(overview, 2)
        self.setCentralWidget(central)
        self.statusBar()
        self.refresh()

    def refresh(self) -> bool:
        try:
            dashboard = self._service.dashboard()
        except VaultError as error:
            self.statusBar().showMessage(str(error))
            return False
        self._fill_entries(dashboard.credentials)
        self._fill_chart(dashboard.daily_counts)
        self._fill_journal(dashboard.activity)
        self.statusBar().clearMessage()
        return True

    def _fill_entries(self, entries: list[Credential]) -> None:
        self.table.setRowCount(0)
        self.table.setRowCount(len(entries))
        self.empty_label.setVisible(not entries)
        for row, entry in enumerate(entries):
            for column, text in enumerate((entry.title, entry.username)):
                item = QTableWidgetItem(text)
                item.setToolTip(f'<qt>{escape(text)}</qt>')
                self.table.setItem(row, column, item)
            actions = QWidget()
            buttons = QHBoxLayout(actions)
            buttons.setContentsMargins(4, 2, 4, 2)
            for name, handler in (
                ('Показать пароль', self.reveal_entry),
                ('Изменить', self.edit_entry),
                ('Удалить', self.delete_entry),
            ):
                button = QPushButton(name)
                button.clicked.connect(lambda checked=False, action=handler, item=entry: action(item))
                buttons.addWidget(button)
            self.table.setCellWidget(row, 2, actions)
            self.table.setRowHeight(row, actions.sizeHint().height())

    def _fill_chart(self, counts: list[DailyCount]) -> None:
        highest = max(1, max((day.count for day in counts), default=0))
        for (date_label, bar, count_label), day in zip(self.chart_rows, counts):
            day_text = day.day.strftime('%d.%m')
            date_label.setText(day_text)
            count_label.setText(str(day.count))
            bar.setAccessibleName(f'Действий {day_text}')
            bar.setRange(0, highest)
            bar.setValue(day.count)

    def _fill_journal(self, events: list[Activity]) -> None:
        self.journal.clear()
        if not events:
            self.journal.addItem('Действий пока нет.')
        for event in events:
            timestamp = event.occurred_at.strftime('%d.%m.%Y %H:%M')
            item = QListWidgetItem(f'{event.label} · {event.title}\n{timestamp} UTC')
            item.setToolTip(f'<qt>{escape(item.text())}</qt>')
            self.journal.addItem(item)

    def add_entry(self) -> None:
        self._open_entry_form(None, 'Запись добавлена.')

    def edit_entry(self, entry: Credential) -> None:
        try:
            current = self._service.get(entry.id)
        except VaultError as error:
            self._show_error(error)
            return
        self._open_entry_form(current, 'Запись изменена.')

    def _open_entry_form(self, entry: Credential | None, status: str) -> None:
        dialog = EntryDialog(self._service, entry, self)
        saved = dialog.exec()
        dialog.password_input.clear()
        dialog.deleteLater()
        if saved and self.refresh():
            self.statusBar().showMessage(status, 3500)

    def reveal_entry(self, entry: Credential) -> None:
        try:
            current, password = self._service.reveal(entry.id)
        except VaultError as error:
            self._show_error(error)
            return
        self.refresh()
        dialog = QDialog(self)
        dialog.setWindowTitle('Пароль')
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        title = plain_label(f'{current.title} · {current.username}')
        title.setWordWrap(True)
        layout.addWidget(title)
        secret = QPlainTextEdit()
        secret.setAccessibleName('Сохранённый пароль')
        secret.setReadOnly(True)
        secret.setPlainText(password)
        secret.setFixedHeight(76)
        layout.addWidget(secret)
        close = QPushButton('Закрыть')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        close.setFocus()
        dialog.exec()
        secret.clear()
        dialog.deleteLater()

    def delete_entry(self, entry: Credential) -> None:
        try:
            current = self._service.get(entry.id)
        except VaultError as error:
            self._show_error(error)
            return
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle('Удалить запись')
        confirmation.setTextFormat(Qt.TextFormat.PlainText)
        confirmation.setText(f'Удалить запись «{current.title}» для логина «{current.username}»?')
        remove = confirmation.addButton('Удалить', QMessageBox.ButtonRole.DestructiveRole)
        cancel = confirmation.addButton('Отмена', QMessageBox.ButtonRole.RejectRole)
        confirmation.setDefaultButton(cancel)
        confirmation.exec()
        if confirmation.clickedButton() != remove:
            return
        try:
            self._service.delete(entry.id)
        except VaultError as error:
            self._show_error(error)
            return
        if self.refresh():
            self.statusBar().showMessage('Запись удалена.', 3500)

    def _show_error(self, error: VaultError) -> None:
        QMessageBox.warning(self, 'Действие не выполнено', str(error))


def main() -> int:
    app = QApplication(sys.argv)
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle('Fusion')
    try:
        service = build_service()
    except VaultError as error:
        QMessageBox.critical(None, 'Ошибка настройки', str(error))
        return 1
    window = MainWindow(service)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
