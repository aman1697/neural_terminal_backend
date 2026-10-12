import asyncio
import os
import uuid

# Must be set before the app (and settings) are imported: signing up many test users would
# otherwise trip the per-IP signup limit. Only affects this test process.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.serve import app  # noqa: E402
from db.connection import d1_client  # noqa: E402

PASSWORD = "PytestPass123!"
_created_emails: list[str] = []


def run_sql(sql: str, params: list | None = None) -> list[dict]:
	return asyncio.run(d1_client.execute(sql, params))


@pytest.fixture(scope="session")
def client():
	with TestClient(app) as test_client:
		yield test_client


@pytest.fixture(scope="session")
def make_user(client):
	"""Returns a factory that signs up + logs in a throwaway user and yields (user_id, auth headers)."""

	def _make() -> tuple[str, dict]:
		email = f"pytest-{uuid.uuid4().hex}@example.com"
		_created_emails.append(email)
		signup = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
		assert signup.status_code == 201, signup.text
		login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
		assert login.status_code == 200, login.text
		return signup.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}

	return _make


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_users():
	yield
	for email in _created_emails:
		rows = run_sql("SELECT id FROM users WHERE email = ?", [email])
		for row in rows:
			for table in ("practice_progress", "notes", "bookmarks", "progress"):
				run_sql(f"DELETE FROM {table} WHERE user_id = ?", [row["id"]])
		run_sql("DELETE FROM users WHERE email = ?", [email])


@pytest.fixture(scope="session")
def user_a(make_user):
	return make_user()


@pytest.fixture(scope="session")
def user_b(make_user):
	return make_user()


@pytest.fixture
def problem_id():
	return f"test-problem-{uuid.uuid4().hex[:12]}"
