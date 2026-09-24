"""Executable acceptance tests: python -m unittest discover -s tests -v."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domain import completion_credit
from app.main import create_app


class CompletionCreditTests(unittest.TestCase):
    def test_only_regular_main_teacher_report_counts(self):
        cases = (
            (1, 1, False, "regular", 1),
            (1, 2, False, "regular", 0),
            (1, 1, False, "supplementary", 0),
            (1, 1, False, "ontact", 0),
            (1, 3, True, "regular", 0),
            (1, 1, True, "regular", 0),
        )
        for main, author, ontact, kind, expected in cases:
            with self.subTest(main=main, author=author, ontact=ontact, kind=kind):
                self.assertEqual(completion_credit(main, author, ontact, kind), expected)


class ReportFlowTests(unittest.TestCase):
    def test_out_of_range_ids_are_validation_errors(self):
        oversized = str(2**63)
        self.assertEqual(self.save(teacher_id=oversized).status_code, 422)
        self.assertEqual(self.client.get(f'/students?student_id={oversized}').status_code, 422)
        self.assertEqual(self.client.get(f'/api/students/{oversized}/reports').status_code, 422)

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.client = TestClient(create_app(Path(self.directory.name) / "test.db"))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def report(self, **changes):
        return {
            "lesson_id": "1",
            "teacher_id": "1",
            "lesson_type": "regular",
            "started_at": "2026-09-18T14:00",
            "ended_at": "2026-09-18T15:00",
            "report_content": "분수의 덧셈을 학습했습니다.",
            "homework_content": "교재 20쪽 풀기",
            **changes,
        }

    def save(self, **changes):
        return self.client.post("/reports", data=self.report(**changes), follow_redirects=False)

    def student(self, student_id=1):
        response = self.client.get(f"/api/students/{student_id}/reports")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_form_and_empty_student_pages_render(self):
        response = self.client.get("/reports/new")
        self.assertEqual(response.status_code, 200)
        for field in self.report():
            self.assertIn(f'name="{field}"', response.text)
        self.assertEqual(self.client.get("/students?student_id=3").status_code, 200)
        self.assertEqual(self.student(3), {"reports": [], "completed_count": 0})

    def test_save_report_redirects_and_increments_count(self):
        response = self.save()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/students?student_id=1&saved=1")
        payload = self.student()
        self.assertEqual(payload["completed_count"], 1)
        self.assertEqual(len(payload["reports"]), 1)
        self.assertEqual(payload["reports"][0]["completion_credit"], 1)
        page = self.client.get("/students?student_id=1")
        self.assertIn(self.report()["report_content"], page.text)
        self.assertIn(self.report()["homework_content"], page.text)

    def test_supplementary_and_ontact_reports_do_not_increment(self):
        self.assertEqual(self.save(teacher_id="2", lesson_type="supplementary").status_code, 303)
        self.assertEqual(self.save(teacher_id="3", lesson_type="ontact").status_code, 303)
        payload = self.student()
        self.assertEqual(len(payload["reports"]), 2)
        self.assertEqual(payload["completed_count"], 0)
        self.assertEqual([row["completion_credit"] for row in payload["reports"]], [0, 0])

    def test_main_teacher_nonregular_report_does_not_increment(self):
        self.assertEqual(self.save(lesson_type="supplementary").status_code, 303)
        self.assertEqual(self.student()["completed_count"], 0)

    def test_ontact_can_write_for_any_lesson(self):
        self.assertEqual(self.save(lesson_id="2", teacher_id="3", lesson_type="ontact").status_code, 303)
        self.assertEqual(len(self.student(2)["reports"]), 1)
        self.assertEqual(self.student(2)["completed_count"], 0)

    def test_students_only_receive_their_own_reports(self):
        self.save()
        self.assertEqual(self.save(lesson_id="2", teacher_id="4", report_content="다른 학생의 보고서").status_code, 303)
        self.assertEqual(len(self.student(1)["reports"]), 1)
        self.assertEqual(len(self.student(2)["reports"]), 1)
        self.assertNotIn("다른 학생의 보고서", self.client.get("/students?student_id=1").text)

    def test_invalid_time_is_rejected_without_losing_content(self):
        for end in ("2026-09-18T13:00", "2026-09-18T14:00", "invalid"):
            with self.subTest(end=end):
                response = self.save(ended_at=end)
                self.assertEqual(response.status_code, 422)
                self.assertIn(self.report()["report_content"], response.text)
        self.assertEqual(self.student()["reports"], [])

    def test_blank_report_content_is_rejected(self):
        self.assertEqual(self.save(report_content="   ").status_code, 422)
        self.assertEqual(self.student()["completed_count"], 0)

    def test_homework_can_be_empty(self):
        self.assertEqual(self.save(homework_content="").status_code, 303)
        self.assertEqual(self.student()["reports"][0]["homework_content"], "")

    def test_invalid_type_is_rejected(self):
        self.assertEqual(self.save(lesson_type="unknown").status_code, 422)

    def test_unrelated_teacher_cannot_write_report(self):
        self.assertEqual(self.save(teacher_id="4").status_code, 403)
        self.assertEqual(self.student()["reports"], [])

    def test_unknown_records_return_not_found(self):
        self.assertEqual(self.save(lesson_id="999").status_code, 404)
        self.assertEqual(self.save(teacher_id="999").status_code, 404)
        self.assertEqual(self.client.get("/api/students/999/reports").status_code, 404)

    def test_duplicate_submission_does_not_inflate_count(self):
        self.assertEqual(self.save().status_code, 303)
        self.assertEqual(self.save().status_code, 409)
        self.assertEqual(self.student()["completed_count"], 1)
        self.assertEqual(len(self.student()["reports"]), 1)

    def test_report_content_is_escaped_in_html(self):
        attack = "<script>alert('test')</script>"
        self.assertEqual(self.save(report_content=attack).status_code, 303)
        response = self.client.get("/students?student_id=1")
        self.assertNotIn(attack, response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertEqual(self.student()["reports"][0]["report_content"], attack)

    def test_reports_persist_when_application_restarts(self):
        self.assertEqual(self.save().status_code, 303)
        with TestClient(create_app(Path(self.directory.name) / "test.db")) as restarted:
            response = restarted.get("/api/students/1/reports")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["completed_count"], 1)
            self.assertEqual(len(response.json()["reports"]), 1)

    def test_two_regular_sessions_accumulate_two_completions(self):
        self.assertEqual(self.save().status_code, 303)
        self.assertEqual(self.save(started_at="2026-09-19T14:00", ended_at="2026-09-19T15:00").status_code, 303)
        self.assertEqual(self.student()["completed_count"], 2)

    def test_nonmain_authors_cannot_get_credit_by_selecting_regular(self):
        for teacher_id in ("2", "3"):
            with self.subTest(teacher_id=teacher_id):
                self.assertEqual(self.save(teacher_id=teacher_id).status_code, 303)
        self.assertEqual(self.student()["completed_count"], 0)
        self.assertEqual(len(self.student()["reports"]), 2)

    def test_timezone_timestamps_and_numeric_dates_are_rejected(self):
        for start in ("2026-09-18T14:00+09:00", "2026-09-18T14:00Z", "1234567890"):
            with self.subTest(start=start):
                self.assertEqual(self.save(started_at=start).status_code, 422)

    def test_oversized_report_and_homework_are_rejected(self):
        for field in ("report_content", "homework_content"):
            with self.subTest(field=field):
                self.assertEqual(self.save(**{field: "가" * 10001}).status_code, 422)
        self.assertEqual(self.student()["reports"], [])

    def test_invalid_identifiers_are_rejected(self):
        for field in ("teacher_id", "lesson_id"):
            for value in ("abc", "0", "-1", "1.5"):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.save(**{field: value}).status_code, 422)
        self.assertEqual(self.client.get("/students?student_id=abc").status_code, 422)
        self.assertEqual(self.client.get("/api/students/abc/reports").status_code, 422)

    def test_unknown_student_has_html_not_found_page(self):
        response = self.client.get("/students?student_id=999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.headers["content-type"])

    def test_database_errors_return_safe_service_unavailable(self):
        secret = "private-database-file-path"
        with patch("app.main.database.student_reports", side_effect=sqlite3.OperationalError(secret)):
            for url in ("/students?student_id=1", "/api/students/1/reports"):
                with self.subTest(url=url), self.assertLogs("app.main", level="ERROR"):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn(secret, response.text)

    def test_home_redirects_to_student_page(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/students")


if __name__ == "__main__":
    unittest.main()
