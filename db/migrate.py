import asyncio
from datetime import datetime, timezone
from pathlib import Path

from db.connection import d1_client

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def run_migrations() -> None:
	await d1_client.execute(
		"CREATE TABLE IF NOT EXISTS schema_migrations "
		"(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
	)
	rows = await d1_client.execute("SELECT name FROM schema_migrations")
	applied = {row["name"] for row in rows}

	for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
		if path.name in applied:
			print(f"Skipping {path.name} (already applied)")
			continue

		print(f"Applying {path.name}...")
		sql = path.read_text()
		for statement in filter(None, (s.strip() for s in sql.split(";"))):
			await d1_client.execute(statement)

		await d1_client.execute(
			"INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
			[path.name, datetime.now(timezone.utc).isoformat()],
		)
	print("Migrations complete.")


if __name__ == "__main__":
	asyncio.run(run_migrations())
