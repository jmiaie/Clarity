import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .assessment import DISCLAIMER, AssessmentError, calculate_profile, public_questions
from .auth import get_current_user
from .database import get_db
from .models import User
from .schemas import AssessmentSubmit
from .timeutil import as_utc, utcnow

router = APIRouter(prefix="/assessment", tags=["Assessment"])


@router.get("/questions")
def get_assessment_questions(current_user: User = Depends(get_current_user)):
    questions = public_questions()
    return {"questions": questions, "total_questions": len(questions), "disclaimer": DISCLAIMER}


@router.post("/submit")
def submit_assessment(
    data: AssessmentSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        profile = calculate_profile(data.answers)
    except AssessmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    current_user.assessment_result = json.dumps(profile)
    current_user.assessment_completed_at = utcnow()
    db.commit()
    return {"profile": profile}


@router.get("/profile")
def get_user_profile(current_user: User = Depends(get_current_user)):
    if not current_user.assessment_result:
        return {"has_profile": False, "profile": None, "completed_at": None}
    completed = current_user.assessment_completed_at
    return {
        "has_profile": True,
        "profile": json.loads(current_user.assessment_result),
        "completed_at": as_utc(completed).isoformat().replace("+00:00", "Z") if completed else None,
    }


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def reset_assessment(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.assessment_result = None
    current_user.assessment_completed_at = None
    db.commit()
    return None
