-- Fictitious demo identities only. Re-running preserves existing reports.
INSERT OR IGNORE INTO Teacher VALUES
    (1, '김선생', '010-0000-0001', 0),
    (2, '이선생', '010-0000-0002', 0),
    (3, '박선생', '010-0000-0003', 1),
    (4, '최선생', '010-0000-0004', 0);
INSERT OR IGNORE INTO Student VALUES
    (1, '김하늘', '010-0000-1001'),
    (2, '이서준', '010-0000-1002'),
    (3, '정다은', '010-0000-1003');
INSERT OR IGNORE INTO Lesson VALUES (1, 1, 1), (2, 2, 4);
INSERT OR IGNORE INTO LessonSupplementaryTeacher VALUES (1, 2);
