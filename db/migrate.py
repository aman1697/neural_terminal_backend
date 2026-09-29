import asyncio
from pathlib import Path

from db.connection import d1_client

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def run_migrations() -> None:
	for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
		print(f"Applying {path.name}...")
		sql = path.read_text()
		for statement in filter(None, (s.strip() for s in sql.split(";"))):
			await d1_client.execute(statement)
	print("Migrations complete.")


if __name__ == "__main__":
	asyncio.run(run_migrations())
