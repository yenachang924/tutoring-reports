"""Input validation and the single source of truth for completion credit."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SQLITE_MAX_ID = 2**63 - 1


class ReportInput(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    lesson_id: int = Field(gt=0, le=SQLITE_MAX_ID)
    teacher_id: int = Field(gt=0, le=SQLITE_MAX_ID)
    lesson_type: Literal['regular', 'supplementary', 'ontact']
    started_at: datetime
    ended_at: datetime
    report_content: str = Field(min_length=1, max_length=10000)
    homework_content: str = Field(default='', max_length=10000)

    @field_validator('started_at', 'ended_at', mode='before')
    @classmethod
    def local_datetime(cls, value):
        # HTML datetime-local is interpreted as Korea local time, never an epoch.
        if not isinstance(value, str) or 'T' not in value:
            raise ValueError('날짜와 시간을 입력해주세요.')
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError('시간대 없는 한국 현지 시간을 입력해주세요.')
        return parsed

    @model_validator(mode='after')
    def chronological(self):
        if self.ended_at <= self.started_at:
            raise ValueError('종료 시간은 시작 시간보다 늦어야 합니다.')
        return self


def completion_credit(main_teacher_id, teacher_id, is_ontact, lesson_type):
    """Ontact takes precedence even if the author is also the main teacher."""
    return int(
        main_teacher_id == teacher_id
        and not is_ontact
        and lesson_type == 'regular'
    )


class ReportError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
