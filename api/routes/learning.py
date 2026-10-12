import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth.authenticate import get_current_user
from db.connection import D1Client, get_db
from db.models import User
from db.schemas import (
	BookmarkCreate,
	BookmarkOut,
	NoteCreate,
	NoteOut,
	NoteUpdate,
	ProgressOut,
	ProgressSet,
	Track,
)
from src.helpers import paths_store

router = APIRouter(tags=["learning"])


def _now() -> str:
	return datetime.now(timezone.utc).isoformat()


async def _require_topic(track: str, topic_id: str) -> None:
	if not await paths_store.topic_exists(track, topic_id):
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Topic '{topic_id}' not found in track '{track}'",
		)


@router.get("/paths/{track}")
async def get_track(track: str, refresh: bool = False):
	return await paths_store.load_track(track, refresh)


@router.get("/paths/{track}/{topic_id}")
async def get_topic(track: str, topic_id: str, refresh: bool = False):
	return await paths_store.load_topic(track, topic_id, refresh)


@router.post("/progress", response_model=ProgressOut)
async def set_progress(
	body: ProgressSet,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await _require_topic(body.track, body.topic_id)
	now = _now()
	await db.execute(
		"INSERT INTO progress (user_id, track, topic_id, status, updated_at) "
		"VALUES (?, ?, ?, ?, ?) "
		"ON CONFLICT(user_id, track, topic_id) DO UPDATE SET "
		"status = excluded.status, updated_at = excluded.updated_at",
		[str(user.id), body.track, body.topic_id, body.status, now],
	)
	return ProgressOut(
		track=body.track,
		topic_id=body.topic_id,
		status=body.status,
		updated_at=datetime.fromisoformat(now),
	)


@router.get("/progress", response_model=list[ProgressOut])
async def get_progress(
	track: Track | None = None,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	sql = "SELECT track, topic_id, status, updated_at FROM progress WHERE user_id = ?"
	params = [str(user.id)]
	if track:
		sql += " AND track = ?"
		params.append(track)
	rows = await db.execute(sql + " ORDER BY updated_at DESC", params)
	return [ProgressOut.model_validate(row) for row in rows]


@router.post("/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
	body: BookmarkCreate,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await _require_topic(body.track, body.topic_id)
	await db.execute(
		"INSERT OR IGNORE INTO bookmarks (user_id, track, topic_id, created_at) VALUES (?, ?, ?, ?)",
		[str(user.id), body.track, body.topic_id, _now()],
	)
	rows = await db.execute(
		"SELECT track, topic_id, created_at FROM bookmarks "
		"WHERE user_id = ? AND track = ? AND topic_id = ?",
		[str(user.id), body.track, body.topic_id],
	)
	return BookmarkOut.model_validate(rows[0])


@router.get("/bookmarks", response_model=list[BookmarkOut])
async def get_bookmarks(
	track: Track | None = None,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	sql = "SELECT track, topic_id, created_at FROM bookmarks WHERE user_id = ?"
	params = [str(user.id)]
	if track:
		sql += " AND track = ?"
		params.append(track)
	rows = await db.execute(sql + " ORDER BY created_at DESC", params)
	return [BookmarkOut.model_validate(row) for row in rows]


@router.delete("/bookmarks", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
	track: Track,
	topic_id: str,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await db.execute(
		"DELETE FROM bookmarks WHERE user_id = ? AND track = ? AND topic_id = ?",
		[str(user.id), track, topic_id],
	)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


_NOTE_COLUMNS = "id, track, topic_id, content, created_at, updated_at"


async def _get_note(db: D1Client, user: User, note_id: str) -> NoteOut:
	rows = await db.execute(
		f"SELECT {_NOTE_COLUMNS} FROM notes WHERE id = ? AND user_id = ?",
		[note_id, str(user.id)],
	)
	if not rows:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
	return NoteOut.model_validate(rows[0])


@router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(
	body: NoteCreate,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await _require_topic(body.track, body.topic_id)
	note_id = str(uuid.uuid4())
	now = _now()
	await db.execute(
		"INSERT INTO notes (id, user_id, track, topic_id, content, created_at, updated_at) "
		"VALUES (?, ?, ?, ?, ?, ?, ?)",
		[note_id, str(user.id), body.track, body.topic_id, body.content, now, now],
	)
	return await _get_note(db, user, note_id)


@router.get("/notes", response_model=list[NoteOut])
async def get_notes(
	track: Track | None = None,
	topic_id: str | None = None,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	sql = f"SELECT {_NOTE_COLUMNS} FROM notes WHERE user_id = ?"
	params = [str(user.id)]
	if track:
		sql += " AND track = ?"
		params.append(track)
	if topic_id:
		sql += " AND topic_id = ?"
		params.append(topic_id)
	rows = await db.execute(sql + " ORDER BY updated_at DESC", params)
	return [NoteOut.model_validate(row) for row in rows]


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(
	note_id: str,
	body: NoteUpdate,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await _get_note(db, user, note_id)
	await db.execute(
		"UPDATE notes SET content = ?, updated_at = ? WHERE id = ? AND user_id = ?",
		[body.content, _now(), note_id, str(user.id)],
	)
	return await _get_note(db, user, note_id)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
	note_id: str,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", [note_id, str(user.id)])
	return Response(status_code=status.HTTP_204_NO_CONTENT)
