import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import create_access_token, get_or_create_oauth_user
from database import get_db
from dependencies import get_current_user
from oauth_service import build_oauth_url, exchange_code
from schemas import TokenResponse, UserOut
from settings import get_settings

router = APIRouter(prefix="/auth")
settings = get_settings()


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str) -> dict:
    if provider not in {"google", "github"}:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    state = secrets.token_urlsafe(16)
    url = build_oauth_url(provider, state)
    return {"authorization_url": url, "state": state}


@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str, code: str = Query(...), db: Session = Depends(get_db)
) -> TokenResponse:
    if provider not in {"google", "github"}:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    if not settings.oauth_enabled:
        raise HTTPException(status_code=400, detail="OAuth credentials are not configured")
    profile = await exchange_code(provider, code)
    user = get_or_create_oauth_user(
        db,
        email=profile["email"],
        name=profile["name"],
        provider=provider,
        provider_subject=profile["sub"],
    )
    token = create_access_token(user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/dev-token", response_model=TokenResponse)
def dev_token(
    email: str = Query(..., description="Development email"),
    name: str = Query(default="Dev User"),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = get_or_create_oauth_user(
        db, email=email, name=name, provider="dev", provider_subject=email
    )
    token = create_access_token(user.email)
    return TokenResponse(access_token=token)
