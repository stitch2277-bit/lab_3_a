from pathlib import Path as FilePath
from secrets import compare_digest, token_urlsafe
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Form, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .errors import DatabaseError, DecryptionError, EntryNotFoundError, ValidationError, VaultError
from .service import PASSWORD_LIMIT, TITLE_LIMIT, USERNAME_LIMIT, PasswordService, build_service


FILES = FilePath(__file__).resolve().parent
STATUS_TEXT = {'created': 'Запись добавлена.', 'updated': 'Запись изменена.', 'deleted': 'Запись удалена.'}
EntryID = Annotated[int, Path(ge=1, le=2**63 - 1)]


class InvalidFormToken(VaultError):
    pass


def create_app(service: PasswordService) -> FastAPI:
    app = FastAPI(title='Менеджер паролей', docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
    app.mount('/static', StaticFiles(directory=FILES / 'static'), name='static')
    templates = Jinja2Templates(directory=FILES / 'templates')
    csrf_token = token_urlsafe(32)

    def render(request: Request, page: str, status_code: int = 200, **context):
        return templates.TemplateResponse(
            request, page, {'csrf_token': csrf_token, **context}, status_code=status_code,
        )

    def render_form(request: Request, entry_id: int | None = None, title='', username='', error=None):
        return render(
            request, 'entry.html', 422 if error else 200, entry_id=entry_id,
            title=title[:TITLE_LIMIT], username=username[:USERNAME_LIMIT], error=error,
            title_limit=TITLE_LIMIT, username_limit=USERNAME_LIMIT, password_limit=PASSWORD_LIMIT,
        )

    def require_token(csrf: Annotated[str, Form()] = '') -> None:
        if not compare_digest(csrf.encode('utf-8'), csrf_token.encode('utf-8')):
            raise InvalidFormToken('Вернитесь к списку и повторите действие.')

    post_guard = [Depends(require_token)]

    @app.middleware('http')
    async def set_response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return render(request, 'message.html', 422, heading='Неверный запрос',
                      message='Откройте форму из списка записей и попробуйте снова.')

    @app.exception_handler(VaultError)
    async def display_error(request: Request, error: VaultError):
        statuses = {
            EntryNotFoundError: 404, DatabaseError: 503, DecryptionError: 422, InvalidFormToken: 403,
        }
        return render(request, 'message.html', statuses.get(type(error), 400),
                      heading='Действие не выполнено', message=str(error))

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request, status: str = ''):
        dashboard = service.dashboard()
        chart_max = max((day.count for day in dashboard.daily_counts), default=0)
        return render(request, 'index.html', dashboard=dashboard, status=STATUS_TEXT.get(status),
                      chart_max=max(1, chart_max))

    @app.get('/entries/new', response_class=HTMLResponse)
    def new_entry(request: Request):
        return render_form(request)

    @app.post('/entries', dependencies=post_guard)
    def add_entry(request: Request, title: Annotated[str, Form()] = '',
                  username: Annotated[str, Form()] = '', password: Annotated[str, Form()] = ''):
        try:
            service.create(title, username, password)
        except ValidationError as error:
            return render_form(request, title=title, username=username, error=str(error))
        return RedirectResponse('/?status=created', status_code=303)

    @app.get('/entries/{entry_id}/edit', response_class=HTMLResponse)
    def edit_entry(request: Request, entry_id: EntryID):
        entry = service.get(entry_id)
        return render_form(request, entry.id, entry.title, entry.username)

    @app.post('/entries/{entry_id}/edit', dependencies=post_guard)
    def save_entry(request: Request, entry_id: EntryID, title: Annotated[str, Form()] = '',
                   username: Annotated[str, Form()] = '', password: Annotated[str, Form()] = ''):
        try:
            service.update(entry_id, title, username, password)
        except ValidationError as error:
            return render_form(request, entry_id, title, username, str(error))
        return RedirectResponse('/?status=updated', status_code=303)

    @app.post('/entries/{entry_id}/reveal', dependencies=post_guard, response_class=HTMLResponse)
    def reveal_entry(request: Request, entry_id: EntryID):
        entry, password = service.reveal(entry_id)
        return render(request, 'reveal.html', entry=entry, password=password)

    @app.get('/entries/{entry_id}/delete', response_class=HTMLResponse)
    def confirm_delete(request: Request, entry_id: EntryID):
        return render(request, 'delete.html', entry=service.get(entry_id))

    @app.post('/entries/{entry_id}/delete', dependencies=post_guard)
    def delete_entry(entry_id: EntryID):
        service.delete(entry_id)
        return RedirectResponse('/?status=deleted', status_code=303)

    @app.get('/exit', response_class=HTMLResponse)
    def exit_view(request: Request):
        return render(request, 'message.html', heading='Работа в браузере завершена',
                      message='Можно закрыть вкладку.')

    return app


def main() -> None:
    try:
        service = build_service()
    except VaultError as error:
        raise SystemExit(str(error)) from None
    uvicorn.run(create_app(service), host='127.0.0.1', port=8000)


if __name__ == '__main__':
    main()
