import re

from fastapi.testclient import TestClient
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QPushButton

from password_manager.desktop import EntryDialog, MainWindow
from password_manager.web import create_app


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.text)[1]


def test_shared_web_and_desktop(service, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    client = TestClient(create_app(service), base_url='http://127.0.0.1')
    window = MainWindow(service)
    window.show()
    try:
        token = csrf(client.get('/entries/new'))
        response = client.post('/entries', data={
            'csrf': token, 'title': 'Почта', 'username': 'student', 'password': 'demo-password',
        })
        assert response.status_code == 200
        assert 'demo-password' not in response.text
        assert window.table.rowCount() == 0
        window.refresh()
        assert window.table.item(0, 0).text() == 'Почта'

        def submit_desktop_form():
            dialog = app.activeModalWidget()
            if isinstance(dialog, EntryDialog):
                dialog.username_input.setText('desktop-user')
                next(button for button in dialog.findChildren(QPushButton)
                     if button.text() == 'Сохранить').click()

        def action_button(label):
            return next(button for button in window.table.cellWidget(0, 2).findChildren(QPushButton)
                        if button.text() == label)

        QTimer.singleShot(0, submit_desktop_form)
        QTimer.singleShot(1000, lambda: reject_modal(app))
        action_button('Изменить').click()
        response = client.get('/')
        assert 'desktop-user' in response.text

        displayed_passwords = []

        def close_revealed_password():
            dialog = app.activeModalWidget()
            if isinstance(dialog, QDialog):
                displayed_passwords.append(dialog.findChild(QPlainTextEdit).toPlainText())
                dialog.accept()

        QTimer.singleShot(0, close_revealed_password)
        QTimer.singleShot(1000, lambda: reject_modal(app))
        action_button('Показать пароль').click()
        assert displayed_passwords == ['demo-password']

        entry_id = service.dashboard().credentials[0].id
        assert client.get(f'/entries/{entry_id}/delete').status_code == 200
        assert client.post(f'/entries/{entry_id}/delete', data={'csrf': token}).status_code == 200
        window.refresh()
        assert window.table.rowCount() == 0
        assert window.journal.count() == 4
    finally:
        window.close()


def reject_modal(app):
    dialog = app.activeModalWidget()
    if isinstance(dialog, QDialog):
        dialog.reject()


def test_web_validation_and_protected_reveal(service):
    client = TestClient(create_app(service), base_url='http://127.0.0.1')
    token = csrf(client.get('/entries/new'))
    data = {'title': '  ', 'username': 'login', 'password': '<secret>'}
    assert client.post('/entries', data=data).status_code == 403
    response = client.post('/entries', data={'csrf': token, **data})
    assert response.status_code == 422
    assert 'Заполните поле' in response.text
    assert 'secret' not in response.text

    entry = service.create('<b>Сервис</b>', 'student', '<secret>')
    assert '&lt;b&gt;Сервис&lt;/b&gt;' in client.get('/').text
    assert 'secret' not in client.get(f'/entries/{entry.id}/edit').text
    path = f'/entries/{entry.id}/reveal'
    assert client.get(path).status_code == 405
    assert client.post(path, data={'csrf': 'wrong'}).status_code == 403
    response = client.post(path, data={'csrf': token})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert '&lt;secret&gt;' in response.text
    assert client.get('/entries/99999/edit').status_code == 404
