import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from auth.authenticate import Authenticator, get_current_user
from db.connection import D1Client, D1QueryError, get_db
from db.models import User
from db.schemas import LoginRequest, RefreshRequest, SignupRequest, TokenResponse, UserOut
from src.helpers.constants import AI_PATH, DL_PATH, ML_PATH
from src.helpers.utils import read_json_file

app = FastAPI()


app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


_paths_cache = {}
_paths_lock = asyncio.Lock()


async def _load_paths_payload():
	files = {
		"ai": AI_PATH,
		"ml": ML_PATH,
		"dl": DL_PATH,
	}

	missing = [str(path) for path in files.values() if not path.exists()]
	if missing:
		raise HTTPException(status_code=500, detail={"missing_files": missing})

	tasks = {name: asyncio.to_thread(read_json_file, path) for name, path in files.items()}
	results = await asyncio.gather(*tasks.values(), return_exceptions=True)

	payload = {}
	for (name, _), result in zip(tasks.items(), results):
		if isinstance(result, Exception):
			raise HTTPException(
				status_code=500,
				detail=f"Failed to load '{name}' paths: {result}",
			)
		payload[name] = result

	return payload



@app.get("/paths")
async def get_paths(refresh: bool = False):
	if _paths_cache and not refresh:
		return _paths_cache

	async with _paths_lock:
		if _paths_cache and not refresh:
			return _paths_cache

		payload = await _load_paths_payload()
		_paths_cache.clear()
		_paths_cache.update(payload)
		return _paths_cache


@app.post("/auth/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: D1Client = Depends(get_db)):
	existing = await Authenticator.get_user_by_email(db, body.email)
	if existing is not None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	user_id = uuid.uuid4()
	now = datetime.now(timezone.utc).isoformat()
	try:
		await db.execute(
			"INSERT INTO users (id, email, hashed_password, is_active, created_at, updated_at) "
			"VALUES (?, ?, ?, ?, ?, ?)",
			[str(user_id), body.email, Authenticator.hash_password(body.password), 1, now, now],
		)
	except D1QueryError:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	return User(
		id=user_id,
		email=body.email,
		hashed_password="",
		is_active=True,
		created_at=datetime.fromisoformat(now),
		updated_at=datetime.fromisoformat(now),
	)


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: D1Client = Depends(get_db)):
	user = await Authenticator.authenticate_user(db, body.email, body.password)
	return TokenResponse(
		access_token=Authenticator.create_access_token(user.id),
		refresh_token=Authenticator.create_refresh_token(user.id),
	)


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: D1Client = Depends(get_db)):
	payload = Authenticator.decode_token(body.refresh_token, expected_type="refresh")

	subject = payload.get("sub")
	try:
		user_id = uuid.UUID(subject)
	except (TypeError, ValueError):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

	user = await Authenticator.get_user_by_id(db, user_id)
	if user is None or not user.is_active:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

	return TokenResponse(
		access_token=Authenticator.create_access_token(user.id),
		refresh_token=Authenticator.create_refresh_token(user.id),
	)


@app.get("/auth/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
	return current_user



