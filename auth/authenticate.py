import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config.settings import settings
from db.connection import D1Client, get_db
from db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized(detail: str) -> HTTPException:
	return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class Authenticator:
	@staticmethod
	def _prehash(password: str) -> bytes:
		return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())

	@classmethod
	def hash_password(cls, password: str) -> str:
		return bcrypt.hashpw(cls._prehash(password), bcrypt.gensalt()).decode("utf-8")

	@classmethod
	def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
		try:
			return bcrypt.checkpw(cls._prehash(plain_password), hashed_password.encode("utf-8"))
		except ValueError:
			return False

	@staticmethod
	def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
		now = datetime.now(timezone.utc)
		payload = {
			"sub": subject,
			"type": token_type,
			"iat": now,
			"exp": now + expires_delta,
			"jti": uuid.uuid4().hex,
		}
		return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

	@classmethod
	def create_access_token(cls, user_id: uuid.UUID) -> str:
		return cls._create_token(
			str(user_id), "access", timedelta(minutes=settings.access_token_expire_minutes)
		)

	@classmethod
	def create_refresh_token(cls, user_id: uuid.UUID) -> str:
		return cls._create_token(
			str(user_id), "refresh", timedelta(days=settings.refresh_token_expire_days)
		)

	@staticmethod
	def decode_token(token: str, expected_type: str) -> dict:
		try:
			payload = jwt.decode(
				token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
			)
		except JWTError:
			raise _unauthorized("Invalid or expired token")
		if payload.get("type") != expected_type:
			raise _unauthorized("Invalid token type")
		return payload

	@staticmethod
	async def is_revoked(db: D1Client, jti: str) -> bool:
		rows = await db.execute("SELECT jti FROM revoked_tokens WHERE jti = ?", [jti])
		return bool(rows)

	@staticmethod
	async def revoke_token(db: D1Client, payload: dict) -> None:
		expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
		await db.execute(
			"INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
			[payload["jti"], expires_at],
		)
		await db.execute(
			"DELETE FROM revoked_tokens WHERE expires_at < ?",
			[datetime.now(timezone.utc).isoformat()],
		)

	@staticmethod
	async def get_user_by_email(db: D1Client, email: str) -> User | None:
		rows = await db.execute("SELECT * FROM users WHERE email = ?", [email])
		return User.from_row(rows[0]) if rows else None

	@staticmethod
	async def get_user_by_id(db: D1Client, user_id: uuid.UUID) -> User | None:
		rows = await db.execute("SELECT * FROM users WHERE id = ?", [str(user_id)])
		return User.from_row(rows[0]) if rows else None

	@classmethod
	async def resolve_user(cls, db: D1Client, payload: dict) -> User:
		try:
			user_id = uuid.UUID(payload.get("sub"))
		except (TypeError, ValueError):
			raise _unauthorized("Invalid token payload")

		user = await cls.get_user_by_id(db, user_id)
		if user is None or not user.is_active:
			raise _unauthorized("User not found or inactive")

		# Tokens issued before a password change must stop working.
		changed = user.password_changed_at
		if changed is not None and int(payload.get("iat", 0)) < int(changed.timestamp()):
			raise _unauthorized("Token no longer valid, please log in again")

		return user

	@classmethod
	async def authenticate_user(cls, db: D1Client, email: str, password: str) -> User:
		user = await cls.get_user_by_email(db, email)
		if user is None or not cls.verify_password(password, user.hashed_password):
			raise _unauthorized("Invalid email or password")
		if not user.is_active:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="User account is inactive",
			)
		return user


async def get_current_user(
	token: str = Depends(oauth2_scheme), db: D1Client = Depends(get_db)
) -> User:
	payload = Authenticator.decode_token(token, expected_type="access")
	return await Authenticator.resolve_user(db, payload)
