import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.connection import get_db
from db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Authenticator:
	_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

	@classmethod
	def hash_password(cls, password: str) -> str:
		return cls._pwd_context.hash(password)

	@classmethod
	def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
		return cls._pwd_context.verify(plain_password, hashed_password)

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
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Invalid or expired token",
			)
		if payload.get("type") != expected_type:
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Invalid token type",
			)
		return payload

	@classmethod
	async def authenticate_user(cls, db: AsyncSession, email: str, password: str) -> User:
		result = await db.execute(select(User).where(User.email == email))
		user = result.scalar_one_or_none()
		if user is None or not cls.verify_password(password, user.hashed_password):
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Invalid email or password",
			)
		if not user.is_active:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="User account is inactive",
			)
		return user


async def get_current_user(
	token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
	payload = Authenticator.decode_token(token, expected_type="access")

	subject = payload.get("sub")
	if subject is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
		)

	try:
		user_id = uuid.UUID(subject)
	except ValueError:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
		)

	result = await db.execute(select(User).where(User.id == user_id))
	user = result.scalar_one_or_none()
	if user is None or not user.is_active:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
		)
	return user
