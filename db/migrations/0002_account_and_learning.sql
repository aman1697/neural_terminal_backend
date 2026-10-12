ALTER TABLE users ADD COLUMN name TEXT;

ALTER TABLE users ADD COLUMN bio TEXT;

ALTER TABLE users ADD COLUMN password_changed_at TEXT;

CREATE TABLE IF NOT EXISTS revoked_tokens (
	jti TEXT PRIMARY KEY,
	expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress (
	user_id TEXT NOT NULL,
	track TEXT NOT NULL,
	topic_id TEXT NOT NULL,
	status TEXT NOT NULL CHECK (status IN ('started', 'completed')),
	updated_at TEXT NOT NULL,
	PRIMARY KEY (user_id, track, topic_id),
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bookmarks (
	user_id TEXT NOT NULL,
	track TEXT NOT NULL,
	topic_id TEXT NOT NULL,
	created_at TEXT NOT NULL,
	PRIMARY KEY (user_id, track, topic_id),
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notes (
	id TEXT PRIMARY KEY,
	user_id TEXT NOT NULL,
	track TEXT NOT NULL,
	topic_id TEXT NOT NULL,
	content TEXT NOT NULL,
	created_at TEXT NOT NULL,
	updated_at TEXT NOT NULL,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_notes_user_topic ON notes(user_id, track, topic_id);
