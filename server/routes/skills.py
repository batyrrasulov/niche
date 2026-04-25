from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import SkillTemplate, User
from schemas import SkillInstallRequest
from services_skills import DEFAULT_SKILLS

router = APIRouter(prefix="/skills")


@router.get("/catalog")
def get_catalog(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_if_empty(db)
    return db.query(SkillTemplate).order_by(SkillTemplate.name.asc()).all()


@router.post("/install")
def install_skill(
    payload: SkillInstallRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _seed_if_empty(db)
    skill = db.query(SkillTemplate).filter(SkillTemplate.slug == payload.slug).first()
    return {"status": "installed" if skill else "missing", "slug": payload.slug}


def _seed_if_empty(db: Session) -> None:
    if db.query(SkillTemplate).count() > 0:
        return
    for seed in DEFAULT_SKILLS:
        db.add(SkillTemplate(**seed))
    db.commit()
