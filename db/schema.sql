PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Teacher (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    is_ontact INTEGER NOT NULL DEFAULT 0 CHECK (is_ontact IN (0, 1))
);
CREATE TABLE IF NOT EXISTS Student (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Lesson (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES Student(id),
    main_teacher_id INTEGER NOT NULL REFERENCES Teacher(id)
);
CREATE TABLE IF NOT EXISTS LessonSupplementaryTeacher (
    lesson_id INTEGER NOT NULL REFERENCES Lesson(id),
    teacher_id INTEGER NOT NULL REFERENCES Teacher(id),
    PRIMARY KEY (lesson_id, teacher_id)
);
CREATE TABLE IF NOT EXISTS Report (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES Lesson(id),
    teacher_id INTEGER NOT NULL REFERENCES Teacher(id),
    lesson_type TEXT NOT NULL CHECK (lesson_type IN ('regular', 'supplementary', 'ontact')),
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL CHECK (ended_at > started_at),
    report_content TEXT NOT NULL CHECK (length(trim(report_content)) BETWEEN 1 AND 10000),
    homework_content TEXT NOT NULL DEFAULT '' CHECK (length(homework_content) <= 10000),
    UNIQUE (lesson_id, teacher_id, lesson_type, started_at)
);
CREATE INDEX IF NOT EXISTS idx_lesson_student ON Lesson(student_id);
CREATE INDEX IF NOT EXISTS idx_report_lesson ON Report(lesson_id);
