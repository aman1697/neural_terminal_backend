import time

from tests.conftest import PASSWORD, run_sql

RECORD_KEYS = {"problem_id", "code", "solved", "solved_at", "updated_at"}
SUMMARY_KEYS = {"problem_id", "solved", "solved_at", "updated_at"}


def put(client, headers, pid, body):
	return client.put(f"/practice/{pid}", json=body, headers=headers)


def test_requires_auth(client, problem_id):
	assert client.put(f"/practice/{problem_id}", json={"code": "x"}).status_code == 401
	assert client.get("/practice").status_code == 401
	assert client.get(f"/practice/{problem_id}").status_code == 401
	assert client.delete(f"/practice/{problem_id}").status_code == 401


def test_put_creates_record(client, user_a, problem_id):
	_, headers = user_a
	response = put(client, headers, problem_id, {"code": "print(1)"})
	assert response.status_code == 200
	data = response.json()
	assert set(data) == RECORD_KEYS
	assert data["problem_id"] == problem_id
	assert data["code"] == "print(1)"
	assert data["solved"] is False
	assert data["solved_at"] is None
	assert data["updated_at"]

	fetched = client.get(f"/practice/{problem_id}", headers=headers)
	assert fetched.status_code == 200
	assert fetched.json() == data


def test_put_updates_existing_record(client, user_a, problem_id):
	_, headers = user_a
	first = put(client, headers, problem_id, {"code": "v1"}).json()
	second = put(client, headers, problem_id, {"code": "v2"}).json()
	assert second["code"] == "v2"
	assert second["updated_at"] >= first["updated_at"]
	assert client.get(f"/practice/{problem_id}", headers=headers).json()["code"] == "v2"


def test_empty_code_is_allowed_and_overwrites(client, user_a, problem_id):
	_, headers = user_a
	put(client, headers, problem_id, {"code": "something"})
	response = put(client, headers, problem_id, {"code": ""})
	assert response.status_code == 200
	assert response.json()["code"] == ""


def test_omitted_code_keeps_stored_code(client, user_a, problem_id):
	_, headers = user_a
	put(client, headers, problem_id, {"code": "keep me"})
	response = put(client, headers, problem_id, {"solved": True})
	assert response.status_code == 200
	assert response.json()["code"] == "keep me"
	assert response.json()["solved"] is True


def test_solved_on_new_row_sets_solved_at(client, user_a, problem_id):
	_, headers = user_a
	data = put(client, headers, problem_id, {"solved": True}).json()
	assert data["solved"] is True
	assert data["solved_at"] is not None
	assert data["code"] == ""


def test_code_only_save_does_not_change_solved(client, user_a, problem_id):
	_, headers = user_a
	put(client, headers, problem_id, {"code": "a"})
	unsolved = put(client, headers, problem_id, {"code": "b"}).json()
	assert unsolved["solved"] is False and unsolved["solved_at"] is None

	put(client, headers, problem_id, {"solved": True})
	still_solved = put(client, headers, problem_id, {"code": "c"}).json()
	assert still_solved["solved"] is True
	assert still_solved["solved_at"] is not None


def test_solved_never_goes_back_to_false(client, user_a, problem_id):
	_, headers = user_a
	put(client, headers, problem_id, {"solved": True})
	only_false = put(client, headers, problem_id, {"solved": False}).json()
	assert only_false["solved"] is True
	code_and_false = put(client, headers, problem_id, {"code": "z", "solved": False}).json()
	assert code_and_false["solved"] is True
	assert code_and_false["code"] == "z"
	assert client.get(f"/practice/{problem_id}", headers=headers).json()["solved"] is True


def test_solved_at_stays_fixed_after_later_saves(client, user_a, problem_id):
	_, headers = user_a
	solved_at = put(client, headers, problem_id, {"solved": True}).json()["solved_at"]
	time.sleep(1.1)
	for body in ({"code": "later"}, {"solved": True}, {"solved": False}, {"code": "x", "solved": True}):
		assert put(client, headers, problem_id, body).json()["solved_at"] == solved_at
	assert client.get(f"/practice/{problem_id}", headers=headers).json()["solved_at"] == solved_at


def test_validation_errors(client, user_a, problem_id):
	_, headers = user_a
	for body in ({}, {"code": None}, {"solved": None}, {"code": None, "solved": None}):
		response = put(client, headers, problem_id, body)
		assert response.status_code == 422, body
		assert "detail" in response.json()
	assert client.get(f"/practice/{problem_id}", headers=headers).status_code == 404

	assert put(client, headers, problem_id, {"code": "x" * 20001}).status_code == 422
	assert put(client, headers, problem_id, {"code": "x" * 20000}).status_code == 200

	assert put(client, headers, "p" * 101, {"code": "x"}).status_code == 422
	assert put(client, headers, "p" * 100, {"code": "x"}).status_code == 200
	client.delete(f"/practice/{'p' * 100}", headers=headers)


def test_get_missing_returns_404_with_detail(client, user_a, problem_id):
	_, headers = user_a
	response = client.get(f"/practice/{problem_id}", headers=headers)
	assert response.status_code == 404
	assert isinstance(response.json()["detail"], str)


def test_list_has_no_code_and_is_newest_first(client, make_user):
	_, headers = make_user()
	put(client, headers, "first", {"code": "secret one"})
	time.sleep(0.05)
	put(client, headers, "second", {"code": "secret two", "solved": True})
	time.sleep(0.05)
	put(client, headers, "first", {"code": "secret one edited"})

	response = client.get("/practice", headers=headers)
	assert response.status_code == 200
	rows = response.json()
	assert [row["problem_id"] for row in rows] == ["first", "second"]
	assert all(set(row) == SUMMARY_KEYS for row in rows)
	assert "secret" not in response.text
	assert rows[1]["solved"] is True and rows[0]["solved"] is False


def test_users_cannot_see_each_others_rows(client, user_a, user_b, problem_id):
	_, headers_a = user_a
	_, headers_b = user_b
	put(client, headers_a, problem_id, {"code": "A's code", "solved": True})

	assert client.get(f"/practice/{problem_id}", headers=headers_b).status_code == 404
	assert problem_id not in [row["problem_id"] for row in client.get("/practice", headers=headers_b).json()]

	b_row = put(client, headers_b, problem_id, {"code": "B's code"}).json()
	assert b_row["code"] == "B's code" and b_row["solved"] is False

	a_row = client.get(f"/practice/{problem_id}", headers=headers_a).json()
	assert a_row["code"] == "A's code" and a_row["solved"] is True

	assert client.delete(f"/practice/{problem_id}", headers=headers_b).status_code == 204
	assert client.get(f"/practice/{problem_id}", headers=headers_a).status_code == 200


def test_delete_is_idempotent_and_resets_state(client, user_a, problem_id):
	_, headers = user_a
	put(client, headers, problem_id, {"code": "work", "solved": True})

	assert client.delete(f"/practice/{problem_id}", headers=headers).status_code == 204
	assert client.delete(f"/practice/{problem_id}", headers=headers).status_code == 204
	assert client.get(f"/practice/{problem_id}", headers=headers).status_code == 404

	fresh = put(client, headers, problem_id, {"code": "again"}).json()
	assert fresh["solved"] is False and fresh["solved_at"] is None


def test_delete_never_seen_problem_is_204(client, user_a, problem_id):
	_, headers = user_a
	assert client.delete(f"/practice/{problem_id}", headers=headers).status_code == 204


def test_account_deletion_removes_practice_rows(client, make_user):
	user_id, headers = make_user()
	put(client, headers, "dot-product", {"code": "x", "solved": True})
	put(client, headers, "relu", {"code": "y"})
	assert len(run_sql("SELECT 1 FROM practice_progress WHERE user_id = ?", [user_id])) == 2

	response = client.request("DELETE", "/users/me", json={"password": PASSWORD}, headers=headers)
	assert response.status_code == 204
	assert run_sql("SELECT 1 FROM practice_progress WHERE user_id = ?", [user_id]) == []


def test_cors_preflight_allows_put_and_delete_from_frontend(client, problem_id):
	for method in ("PUT", "DELETE"):
		response = client.options(
			f"/practice/{problem_id}",
			headers={
				"Origin": "http://localhost:8080",
				"Access-Control-Request-Method": method,
				"Access-Control-Request-Headers": "authorization,content-type",
			},
		)
		assert response.status_code == 200, method
		assert response.headers["access-control-allow-origin"] == "http://localhost:8080"
		assert method in response.headers["access-control-allow-methods"]
