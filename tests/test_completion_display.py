"""Completion explanations and database constraints tested against real SQLite."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from fastapi.testclient import TestClient

from app.database import connection, initialize
from app.main import create_app


class CompletionDisplayTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = TestClient(create_app(Path(directory.name) / "display.db"))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def assert_explanation(self, teacher_id, lesson_type, expected_reason, credit):
        response = self.client.post("/reports", data={
            "lesson_id": "1",
            "teacher_id": str(teacher_id),
            "lesson_type": lesson_type,
            "started_at": "2026-09-24T14:00",
            "ended_at": "2026-09-24T15:00",
            "report_content": "완료 횟수 표시 확인",
            "homework_content": "",
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        page = self.client.get("/students?student_id=1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(expected_reason, page.text)
        summary = self.client.get("/api/students/1/reports").json()
        self.assertEqual(summary["completed_count"], credit)

    def test_main_regular_report_explains_one_credit(self):
        self.assert_explanation(
            1, "regular", "주 선생님의 정규 수업으로 1회 반영됩니다.", 1
        )

    def test_supplementary_author_regular_report_explains_zero_credit(self):
        self.assert_explanation(
            2, "regular",
            "이 수업의 주 선생님이 작성한 보고서가 아니므로 횟수에 반영되지 않습니다.", 0
        )

    def test_ontact_regular_report_explains_zero_credit(self):
        self.assert_explanation(
            3, "regular", "온택트 선생님의 보고서는 횟수에 반영되지 않습니다.", 0
        )

    def test_main_supplementary_report_explains_zero_credit(self):
        self.assert_explanation(
            1, "supplementary", "정규 수업 보고서가 아니므로 횟수에 반영되지 않습니다.", 0
        )


class DatabaseConstraintTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "constraints.db"
        initialize(self.path)

    def insert_report(self, lesson_id=1):
        with connection(self.path) as db:
            db.execute("""
                INSERT INTO Report (lesson_id, teacher_id, lesson_type, started_at,
                    ended_at, report_content, homework_content)
                VALUES (?, 1, 'regular', '2026-09-24T14:00:00',
                    '2026-09-24T15:00:00', 'DB 제약 확인', '')
            """, (lesson_id,))

    def test_foreign_key_rejects_report_for_nonexistent_lesson(self):
        with self.assertRaises(sqlite3.IntegrityError) as error:
            self.insert_report(lesson_id=999)
        self.assertEqual(error.exception.sqlite_errorname, "SQLITE_CONSTRAINT_FOREIGNKEY")

    def test_duplicate_is_rejected_even_without_application_precheck(self):
        self.insert_report()
        with self.assertRaises(sqlite3.IntegrityError) as error:
            self.insert_report()
        self.assertEqual(error.exception.sqlite_errorname, "SQLITE_CONSTRAINT_UNIQUE")
        with connection(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM Report").fetchone()[0], 1)
