import math
import re
import time
from collections import deque
from typing import NamedTuple

from fastapi import Depends, HTTPException, Request, status

from auth.authenticate import get_current_user
from config.settings import settings
from db.models import User

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_SPEC_PATTERN = re.compile(r"^(\d+)/(\d+)([smhd])$")
_SWEEP_INTERVAL_SECONDS = 60


class Limit(NamedTuple):
	max_requests: int
	window_seconds: int


def parse_limit(spec: str) -> Limit:
	"""Parse "<count>/<number><unit>", e.g. "5/1m" or "10/1h". Raises at startup if malformed."""
	match = _SPEC_PATTERN.match(spec.strip())
	if not match:
		raise ValueError(f"Invalid rate limit '{spec}', expected e.g. '5/1m' or '10/1h'")
	count, amount, unit = match.groups()
	return Limit(int(count), int(amount) * _UNIT_SECONDS[unit])


class SlidingWindowLimiter:
	def __init__(self) -> None:
		self._hits: dict[str, tuple[int, deque[float]]] = {}
		self._last_sweep = time.monotonic()

	def _sweep(self, now: float) -> None:
		if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
			return
		self._last_sweep = now
		stale = [
			key for key, (window, hits) in self._hits.items()
			if not hits or hits[-1] <= now - window
		]
		for key in stale:
			del self._hits[key]

	def hit(self, key: str, limit: Limit) -> int:
		"""Record a request. Returns 0 if allowed, otherwise seconds until a slot frees up."""
		now = time.monotonic()
		self._sweep(now)

		entry = self._hits.get(key)
		if entry is None:
			hits: deque[float] = deque()
			self._hits[key] = (limit.window_seconds, hits)
		else:
			hits = entry[1]

		cutoff = now - limit.window_seconds
		while hits and hits[0] <= cutoff:
			hits.popleft()

		if len(hits) >= limit.max_requests:
			return max(1, math.ceil(hits[0] + limit.window_seconds - now))

		hits.append(now)
		return 0

	def reset(self, key: str) -> None:
		self._hits.pop(key, None)


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
	if settings.trust_proxy_headers:
		forwarded = request.headers.get("x-forwarded-for")
		if forwarded:
			# The last entry is the one appended by our own trusted proxy; earlier ones are client-controlled.
			return forwarded.split(",")[-1].strip()
	return request.client.host if request.client else "unknown"


def enforce(key: str, limit: Limit) -> None:
	if not settings.rate_limit_enabled:
		return
	retry_after = limiter.hit(key, limit)
	if retry_after:
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail=f"Too many requests. Try again in {retry_after} seconds.",
			headers={"Retry-After": str(retry_after)},
		)


def limit_by_ip(scope: str, limit: Limit):
	async def dependency(request: Request) -> None:
		enforce(f"{scope}:{client_ip(request)}", limit)

	return dependency


def limit_by_user(scope: str, limit: Limit):
	async def dependency(user: User = Depends(get_current_user)) -> None:
		enforce(f"{scope}:{user.id}", limit)

	return dependency
