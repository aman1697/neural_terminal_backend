from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.rate_limit import limit_by_user, parse_limit
from auth.authenticate import Authenticator, get_current_user
from config.settings import settings
from db.connection import D1Client, get_db
from db.models import User
from db.schemas import (
	ChangePasswordRequest,
	DeleteAccountRequest,
	TokenResponse,
	UpdateProfileRequest,
	UserOut,
)

router = APIRouter(prefix="/users", tags=["users"])

_sensitive_limit = limit_by_user("sensitive", parse_limit(settings.rate_limit_sensitive))


@router.patch("/me", response_model=UserOut)
async def update_me(
	body: UpdateProfileRequest,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	fields = body.model_dump(exclude_unset=True)
	if not fields:
		return user

	# Column names come from UpdateProfileRequest's fields only, never from user input.
	assignments = ", ".join(f"{column} = ?" for column in fields)
	now = datetime.now(timezone.utc).isoformat()
	await db.execute(
		f"UPDATE users SET {assignments}, updated_at = ? WHERE id = ?",
		[*fields.values(), now, str(user.id)],
	)
	return await Authenticator.get_user_by_id(db, user.id)


@router.post(
	"/me/change-password",
	response_model=TokenResponse,
	dependencies=[Depends(_sensitive_limit)],
)
async def change_password(
	body: ChangePasswordRequest,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	if not Authenticator.verify_password(body.current_password, user.hashed_password):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
	if body.current_password == body.new_password:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="New password must be different from the current password",
		)

	now = datetime.now(timezone.utc).isoformat()
	await db.execute(
		"UPDATE users SET hashed_password = ?, password_changed_at = ?, updated_at = ? WHERE id = ?",
		[Authenticator.hash_password(body.new_password), now, now, str(user.id)],
	)

	return TokenResponse(
		access_token=Authenticator.create_access_token(user.id),
		refresh_token=Authenticator.create_refresh_token(user.id),
	)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_sensitive_limit)])
async def delete_me(
	body: DeleteAccountRequest,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	if not Authenticator.verify_password(body.password, user.hashed_password):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect")

	user_id = str(user.id)
	for table in ("notes", "bookmarks", "progress", "practice_progress"):
		await db.execute(f"DELETE FROM {table} WHERE user_id = ?", [user_id])
	await db.execute("DELETE FROM users WHERE id = ?", [user_id])

	return Response(status_code=status.HTTP_204_NO_CONTENT)
