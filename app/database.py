"""Small SQLite repository. Each operation opens and closes its connection."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.domain import ReportError, ReportInput, completion_credit

ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as db:
        db.executescript((ROOT / 'db/schema.sql').read_text(encoding='utf-8'))
        db.executescript((ROOT / 'db/seed.sql').read_text(encoding='utf-8'))


def form_options(path):
    with connection(path) as db:
        teachers = db.execute('SELECT id, name, is_ontact FROM Teacher ORDER BY id').fetchall()
        lessons = db.execute('''
            SELECT l.id, s.name AS student_name, t.name AS main_teacher_name
            FROM Lesson l JOIN Student s ON l.student_id=s.id
            JOIN Teacher t ON l.main_teacher_id=t.id ORDER BY l.id
        ''').fetchall()
        return {'teachers': teachers, 'lessons': lessons}


def student_options(path):
    with connection(path) as db:
        return db.execute('SELECT id, name FROM Student ORDER BY id').fetchall()


def allowed_lesson(db, report):
    lesson = db.execute('SELECT * FROM Lesson WHERE id=?', (report.lesson_id,)).fetchone()
    teacher = db.execute('SELECT * FROM Teacher WHERE id=?', (report.teacher_id,)).fetchone()
    if not lesson or not teacher:
        raise ReportError('수업 또는 선생님을 찾을 수 없습니다.', 404)
    assigned = db.execute('''
        SELECT 1 FROM LessonSupplementaryTeacher WHERE lesson_id=? AND teacher_id=?
    ''', (report.lesson_id, report.teacher_id)).fetchone()
    if not (teacher['is_ontact'] or lesson['main_teacher_id'] == report.teacher_id or assigned):
        raise ReportError('이 선생님은 선택한 수업의 보고서를 작성할 수 없습니다.', 403)
    return lesson


def save_report(path, report: ReportInput):
    try:
        with connection(path) as db:
            lesson = allowed_lesson(db, report)
            db.execute('''
                INSERT INTO Report (lesson_id, teacher_id, lesson_type, started_at,
                    ended_at, report_content, homework_content) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (report.lesson_id, report.teacher_id, report.lesson_type,
                  report.started_at.isoformat(), report.ended_at.isoformat(),
                  report.report_content, report.homework_content))
            return lesson['student_id']
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorname == 'SQLITE_CONSTRAINT_UNIQUE':
            raise ReportError('같은 수업·선생님·종류·시작 시간의 보고서가 이미 있습니다.', 409) from error
        raise ReportError('보고서 데이터를 확인해주세요.', 422) from error


def student_reports(path, student_id):
    with connection(path) as db:
        student = db.execute('SELECT id, name FROM Student WHERE id=?', (student_id,)).fetchone()
        if not student:
            raise ReportError('학생을 찾을 수 없습니다.', 404)
        rows = db.execute('''
            SELECT r.*, t.name AS teacher_name, t.is_ontact, l.main_teacher_id
            FROM Report r JOIN Lesson l ON r.lesson_id=l.id
            JOIN Teacher t ON r.teacher_id=t.id
            WHERE l.student_id=? ORDER BY r.started_at DESC, r.id DESC
        ''', (student_id,)).fetchall()
    reports = [dict(row) | {'completion_credit': completion_credit(
        row['main_teacher_id'], row['teacher_id'], row['is_ontact'], row['lesson_type']
    )} for row in rows]
    return dict(student), reports, sum(row['completion_credit'] for row in reports)
