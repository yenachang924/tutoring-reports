"""HTTP endpoints. Run from the project root: python -m uvicorn app.main:app."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Form, Request, Query, Path as PathParameter
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app import database
from app.domain import SQLITE_MAX_ID, ReportError, ReportInput

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=ROOT / 'frontend/templates')
logger = logging.getLogger(__name__)


def render_form(request, path, values=None, error=None, status_code=200):
    return templates.TemplateResponse(request=request, name='new_report.html', context={
        **database.form_options(path), 'values': values or {}, 'error': error,
    }, status_code=status_code)


def install_handlers(app):
    @app.exception_handler(ReportError)
    async def report_error(request: Request, error: ReportError):
        if request.url.path.startswith('/api/'):
            return JSONResponse({'error': str(error)}, status_code=error.status_code)
        return templates.TemplateResponse(request=request, name='error.html',
            context={'message': str(error)}, status_code=error.status_code)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, error: sqlite3.Error):
        logger.error('Database operation failed: %s', type(error).__name__)
        message = '데이터 처리에 실패했습니다. 잠시 후 다시 시도해주세요.'
        if request.url.path.startswith('/api/'):
            return JSONResponse({'error': message}, status_code=503)
        return templates.TemplateResponse(request=request, name='error.html',
            context={'message': message}, status_code=503)


def install_routes(app, path):
    @app.get('/')
    def home():
        return RedirectResponse('/students', status_code=303)

    @app.get('/reports/new')
    def new_report(request: Request):
        return render_form(request, path)

    @app.post('/reports')
    def write_report(request: Request, lesson_id: str = Form(''), teacher_id: str = Form(''),
                     lesson_type: str = Form(''), started_at: str = Form(''), ended_at: str = Form(''),
                     report_content: str = Form(''), homework_content: str = Form('')):
        values = dict(lesson_id=lesson_id, teacher_id=teacher_id, lesson_type=lesson_type,
                      started_at=started_at, ended_at=ended_at,
                      report_content=report_content, homework_content=homework_content)
        try:
            report = ReportInput(**values)
            student_id = database.save_report(path, report)
        except ValidationError:
            return render_form(request, path, values,
                '입력값을 확인해주세요. 본문은 1~10,000자, 숙제는 최대 10,000자이며 종료는 시작보다 늦어야 합니다.', 422)
        except ReportError as error:
            return render_form(request, path, values, str(error), error.status_code)
        return RedirectResponse(f'/students?student_id={student_id}&saved=1', status_code=303)

    @app.get('/students')
    def students(request: Request, student_id: int = Query(1, gt=0, le=SQLITE_MAX_ID), saved: bool = False):
        student, reports, count = database.student_reports(path, student_id)
        return templates.TemplateResponse(request=request, name='students.html', context={
            'students': database.student_options(path), 'selected_student': student,
            'reports': reports, 'completed_count': count, 'saved': saved,
        })

    @app.get('/api/students/{student_id}/reports')
    def api_reports(student_id: int = PathParameter(gt=0, le=SQLITE_MAX_ID)):
        _, reports, count = database.student_reports(path, student_id)
        return {'reports': reports, 'completed_count': count}


def create_app(db_path=None):
    path = Path(db_path or os.environ.get('DATABASE_PATH', ROOT / 'data/tutoring.db'))

    @asynccontextmanager
    async def lifespan(app):
        database.initialize(path)
        yield

    app = FastAPI(title='강쌤과외 수업 기록', lifespan=lifespan)
    app.mount('/static', StaticFiles(directory=ROOT / 'frontend/static'), name='static')
    install_handlers(app)
    install_routes(app, path)
    return app


app = create_app()
