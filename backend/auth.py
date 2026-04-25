from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import User
from settings import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
settings = get_settings()


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Missing subject")
        return sub
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def get_or_create_oauth_user(
    db: Session, *, email: str, name: str, provider: str, provider_subject: str
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.name = name
        user.oauth_provider = provider
        user.oauth_subject = provider_subject
        db.commit()
        db.refresh(user)
        return user
    user = User(email=email, name=name, oauth_provider=provider, oauth_subject=provider_subject)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
