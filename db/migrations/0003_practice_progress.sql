CREATE TABLE IF NOT EXISTS practice_progress (
	user_id TEXT NOT NULL,
	problem_id TEXT NOT NULL,
	code TEXT NOT NULL DEFAULT '',
	solved INTEGER NOT NULL DEFAULT 0,
	solved_at TEXT,
	updated_at TEXT NOT NULL,
	PRIMARY KEY (user_id, problem_id),
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
