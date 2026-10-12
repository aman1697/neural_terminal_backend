import asyncio

from fastapi import HTTPException

from src.helpers.constants import AI_PATH, DL_PATH, ML_PATH
from src.helpers.utils import read_json_file

TRACK_FILES = {
	"ai": AI_PATH,
	"ml": ML_PATH,
	"dl": DL_PATH,
}

_cache: dict[str, list] = {}
_lock = asyncio.Lock()


async def _load_all_from_disk() -> dict[str, list]:
	missing = [str(path) for path in TRACK_FILES.values() if not path.exists()]
	if missing:
		raise HTTPException(status_code=500, detail={"missing_files": missing})

	tasks = {name: asyncio.to_thread(read_json_file, path) for name, path in TRACK_FILES.items()}
	results = await asyncio.gather(*tasks.values(), return_exceptions=True)

	payload = {}
	for name, result in zip(tasks, results):
		if isinstance(result, Exception):
			raise HTTPException(
				status_code=500,
				detail=f"Failed to load '{name}' paths: {result}",
			)
		payload[name] = result or []

	return payload


async def load_all(refresh: bool = False) -> dict[str, list]:
	if _cache and not refresh:
		return _cache

	async with _lock:
		if _cache and not refresh:
			return _cache

		payload = await _load_all_from_disk()
		_cache.clear()
		_cache.update(payload)
		return _cache


async def load_track(track: str, refresh: bool = False) -> list:
	if track not in TRACK_FILES:
		raise HTTPException(status_code=404, detail=f"Unknown track '{track}'")
	return (await load_all(refresh))[track]


async def topic_exists(track: str, topic_id: str) -> bool:
	topics = await load_track(track)
	return any(topic.get("id") == topic_id for topic in topics)
