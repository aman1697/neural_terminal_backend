import asyncio

from fastapi import HTTPException

from src.helpers.constants import AI_PATH, DL_PATH, LEARNING_PATHS, ML_PATH
from src.helpers.utils import read_json_file

TRACK_FILES = {
	"ai": AI_PATH,
	"ml": ML_PATH,
	"dl": DL_PATH,
}

_cache: dict[str, list] = {}
_topic_cache: dict[tuple[str, str], dict] = {}
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
		_topic_cache.clear()
		return _cache


async def load_track(track: str, refresh: bool = False) -> list:
	if track not in TRACK_FILES:
		raise HTTPException(status_code=404, detail=f"Unknown track '{track}'")
	return (await load_all(refresh))[track]


async def topic_exists(track: str, topic_id: str) -> bool:
	topics = await load_track(track)
	return any(topic.get("id") == topic_id for topic in topics)


async def load_topic(track: str, topic_id: str, refresh: bool = False) -> dict:
	# Only ids listed in the track index are served, so topic_id never reaches the filesystem unchecked.
	topics = await load_track(track, refresh)
	if not any(topic.get("id") == topic_id for topic in topics):
		raise HTTPException(
			status_code=404,
			detail=f"Topic '{topic_id}' not found in track '{track}'",
		)

	key = (track, topic_id)
	if key in _topic_cache:
		return _topic_cache[key]

	path = LEARNING_PATHS / track / f"{topic_id}.json"
	try:
		topic = await asyncio.to_thread(read_json_file, path)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Failed to load topic '{topic_id}': {exc}")
	if not topic:
		raise HTTPException(status_code=500, detail=f"Content for topic '{topic_id}' is missing")

	_topic_cache[key] = topic
	return topic
