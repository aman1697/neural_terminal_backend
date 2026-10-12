import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
	id: uuid.UUID
	email: str
	hashed_password: str
	is_active: bool
	created_at: datetime
	updated_at: datetime
	name: str | None = None
	bio: str | None = None
	password_changed_at: datetime | None = None

	@classmethod
	def from_row(cls, row: dict) -> "User":
		changed = row.get("password_changed_at")
		return cls(
			id=uuid.UUID(row["id"]),
			email=row["email"],
			hashed_password=row["hashed_password"],
			is_active=bool(row["is_active"]),
			created_at=datetime.fromisoformat(row["created_at"]),
			updated_at=datetime.fromisoformat(row["updated_at"]),
			name=row.get("name"),
			bio=row.get("bio"),
			password_changed_at=datetime.fromisoformat(changed) if changed else None,
		)
