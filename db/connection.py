from typing import Any

import httpx

from config.settings import settings


class D1QueryError(RuntimeError):
	pass


class D1Client:
	def __init__(self) -> None:
		self._url = settings.d1_query_url
		self._headers = {
			"Authorization": f"Bearer {settings.cloudflare_api_token}",
			"Content-Type": "application/json",
		}

	async def execute(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
		async with httpx.AsyncClient(timeout=10) as client:
			response = await client.post(
				self._url,
				headers=self._headers,
				json={"sql": sql, "params": params or []},
			)

		try:
			response.raise_for_status()
		except httpx.HTTPStatusError as exc:
			raise D1QueryError(f"D1 request failed: {exc}") from exc

		body = response.json()
		if not body.get("success"):
			raise D1QueryError(f"D1 query failed: {body.get('errors')}")

		results = body.get("result") or []
		if not results:
			return []

		result = results[0]
		if not result.get("success", True):
			raise D1QueryError(f"D1 query failed: {result.get('error')}")

		return result.get("results", [])


d1_client = D1Client()


async def get_db() -> D1Client:
	return d1_client
