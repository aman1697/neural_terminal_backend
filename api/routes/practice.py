from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from auth.authenticate import get_current_user
from db.connection import D1Client, get_db
from db.models import User
from db.schemas import PracticeRecord, PracticeSummary, PracticeUpdate

router = APIRouter(prefix="/practice", tags=["practice"])

ProblemId = Annotated[str, Path(min_length=1, max_length=100)]

# Single atomic upsert: solved never goes true -> false, solved_at is set once, code is kept when omitted.
_UPSERT_SQL = (
	"INSERT INTO practice_progress (user_id, problem_id, code, solved, solved_at, updated_at) "
	"VALUES (?, ?, ?, ?, ?, ?) "
	"ON CONFLICT(user_id, problem_id) DO UPDATE SET "
	"code = CASE WHEN ? = 1 THEN excluded.code ELSE practice_progress.code END, "
	"solved = MAX(practice_progress.solved, excluded.solved), "
	"solved_at = CASE "
	"WHEN practice_progress.solved = 1 THEN practice_progress.solved_at "
	"WHEN excluded.solved = 1 THEN excluded.solved_at "
	"ELSE NULL END, "
	"updated_at = excluded.updated_at "
	"RETURNING problem_id, code, solved, solved_at, updated_at"
)


@router.put("/{problem_id}", response_model=PracticeRecord)
async def save_practice(
	problem_id: ProblemId,
	body: PracticeUpdate,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	now = datetime.now(timezone.utc).isoformat()
	solved = 1 if body.solved else 0
	rows = await db.execute(
		_UPSERT_SQL,
		[
			str(user.id),
			problem_id,
			body.code or "",
			solved,
			now if solved else None,
			now,
			1 if body.code is not None else 0,
		],
	)
	return PracticeRecord.model_validate(rows[0])


@router.get("", response_model=list[PracticeSummary])
async def list_practice(
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	rows = await db.execute(
		"SELECT problem_id, solved, solved_at, updated_at FROM practice_progress "
		"WHERE user_id = ? ORDER BY updated_at DESC",
		[str(user.id)],
	)
	return [PracticeSummary.model_validate(row) for row in rows]


@router.get("/{problem_id}", response_model=PracticeRecord)
async def get_practice(
	problem_id: ProblemId,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	rows = await db.execute(
		"SELECT problem_id, code, solved, solved_at, updated_at FROM practice_progress "
		"WHERE user_id = ? AND problem_id = ?",
		[str(user.id), problem_id],
	)
	if not rows:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"No practice record for problem '{problem_id}'",
		)
	return PracticeRecord.model_validate(rows[0])


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_practice(
	problem_id: ProblemId,
	user: User = Depends(get_current_user),
	db: D1Client = Depends(get_db),
):
	await db.execute(
		"DELETE FROM practice_progress WHERE user_id = ? AND problem_id = ?",
		[str(user.id), problem_id],
	)
	return Response(status_code=status.HTTP_204_NO_CONTENT)
