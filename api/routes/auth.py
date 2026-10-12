import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.rate_limit import client_ip, enforce, limit_by_ip, limiter, parse_limit
from auth.authenticate import Authenticator, get_current_user
from config.settings import settings
from db.connection import D1Client, D1QueryError, get_db
from db.models import User
from db.schemas import (
	LoginRequest,
	LogoutRequest,
	RefreshRequest,
	SignupRequest,
	TokenResponse,
	UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_ACCOUNT_LIMIT = parse_limit(settings.rate_limit_login_account)


def _token_pair(user_id: uuid.UUID) -> TokenResponse:
	return TokenResponse(
		access_token=Authenticator.create_access_token(user_id),
		refresh_token=Authenticator.create_refresh_token(user_id),
	)


@router.post(
	"/signup",
	response_model=UserOut,
	status_code=status.HTTP_201_CREATED,
	dependencies=[Depends(limit_by_ip("signup", parse_limit(settings.rate_limit_signup)))],
)
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


@router.post(
	"/login",
	response_model=TokenResponse,
	dependencies=[Depends(limit_by_ip("login-ip", parse_limit(settings.rate_limit_login_ip)))],
)
async def login(body: LoginRequest, request: Request, db: D1Client = Depends(get_db)):
	# Keyed by IP + email so an attacker can't lock a victim out from their own IP.
	account_key = f"login-account:{client_ip(request)}:{body.email.lower()}"
	enforce(account_key, LOGIN_ACCOUNT_LIMIT)

	user = await Authenticator.authenticate_user(db, body.email, body.password)
	limiter.reset(account_key)
	return _token_pair(user.id)


@router.post(
	"/refresh",
	response_model=TokenResponse,
	dependencies=[Depends(limit_by_ip("refresh", parse_limit(settings.rate_limit_refresh)))],
)
async def refresh(body: RefreshRequest, db: D1Client = Depends(get_db)):
	payload = Authenticator.decode_token(body.refresh_token, expected_type="refresh")

	if await Authenticator.is_revoked(db, payload["jti"]):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

	user = await Authenticator.resolve_user(db, payload)

	await Authenticator.revoke_token(db, payload)
	return _token_pair(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: D1Client = Depends(get_db)):
	payload = Authenticator.decode_token(body.refresh_token, expected_type="refresh")
	await Authenticator.revoke_token(db, payload)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
	return current_user
