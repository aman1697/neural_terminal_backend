import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Track = Literal["ai", "ml", "dl"]


class SignupRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str


class TokenResponse(BaseModel):
	access_token: str
	refresh_token: str
	token_type: str = "bearer"


class RefreshRequest(BaseModel):
	refresh_token: str


class LogoutRequest(BaseModel):
	refresh_token: str


class UserOut(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	email: EmailStr
	is_active: bool
	created_at: datetime
	name: str | None = None
	bio: str | None = None


class UpdateProfileRequest(BaseModel):
	name: str | None = Field(default=None, max_length=100)
	bio: str | None = Field(default=None, max_length=500)


class ChangePasswordRequest(BaseModel):
	current_password: str
	new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
	password: str


class ProgressSet(BaseModel):
	track: Track
	topic_id: str = Field(min_length=1, max_length=200)
	status: Literal["started", "completed"]


class ProgressOut(BaseModel):
	track: Track
	topic_id: str
	status: Literal["started", "completed"]
	updated_at: datetime


class BookmarkCreate(BaseModel):
	track: Track
	topic_id: str = Field(min_length=1, max_length=200)


class BookmarkOut(BaseModel):
	track: Track
	topic_id: str
	created_at: datetime


class NoteCreate(BaseModel):
	track: Track
	topic_id: str = Field(min_length=1, max_length=200)
	content: str = Field(min_length=1, max_length=5000)


class NoteUpdate(BaseModel):
	content: str = Field(min_length=1, max_length=5000)


class NoteOut(BaseModel):
	id: str
	track: Track
	topic_id: str
	content: str
	created_at: datetime
	updated_at: datetime


class PracticeUpdate(BaseModel):
	code: str | None = Field(default=None, max_length=20000)
	solved: bool | None = None

	@model_validator(mode="after")
	def _require_at_least_one(self):
		if self.code is None and self.solved is None:
			raise ValueError("Provide at least one of 'code' or 'solved'")
		return self


class PracticeSummary(BaseModel):
	problem_id: str
	solved: bool
	solved_at: datetime | None = None
	updated_at: datetime


class PracticeRecord(PracticeSummary):
	code: str
