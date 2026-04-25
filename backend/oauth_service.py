from urllib.parse import urlencode
import httpx

from settings import get_settings

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def build_oauth_url(provider: str, state: str) -> str:
    redirect_uri = f"{settings.oauth_redirect_base}/api/v1/auth/oauth/{provider}/callback"
    if provider == "google":
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    if provider == "github":
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{GITHUB_AUTH_URL}?{urlencode(params)}"
    raise ValueError("Unsupported provider")


async def exchange_code(provider: str, code: str) -> dict:
    redirect_uri = f"{settings.oauth_redirect_base}/api/v1/auth/oauth/{provider}/callback"
    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "google":
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]
            profile_resp = await client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
            return {
                "email": profile["email"],
                "name": profile.get("name") or profile["email"],
                "sub": profile.get("sub") or profile["email"],
            }
        if provider == "github":
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]
            profile_resp = await client.get(
                GITHUB_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
            email_resp = await client.get(
                GITHUB_EMAILS_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            email_resp.raise_for_status()
            primary_email = next((e["email"] for e in email_resp.json() if e.get("primary")), None)
            email = primary_email or profile.get("email")
            if not email:
                raise ValueError("GitHub email not available")
            return {
                "email": email,
                "name": profile.get("name") or profile.get("login") or email,
                "sub": str(profile.get("id") or email),
            }
    raise ValueError("Unsupported provider")
