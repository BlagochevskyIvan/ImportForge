from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from src.auth.jwt import get_user_id_from_jwt
from src.core.config import AUTH_ALLOWED_ORIGINS
from src.db.database import get_session
from src.db.user_crud import get_user_by_id
from src.schemas.users import UserRead

bearer = HTTPBearer(auto_error=False)


def require_auth_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None and (referer := request.headers.get("referer")):
        try:
            parsed = urlsplit(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
        except ValueError:
            raise HTTPException(403, "Untrusted authentication origin") from None
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin is not None and origin not in AUTH_ALLOWED_ORIGINS
    ):
        raise HTTPException(403, "Untrusted authentication origin")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UserRead:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        user_id = get_user_id_from_jwt(credentials.credentials)
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    async with get_session() as session:
        user = await get_user_by_id(session, user_id)

        if user is None or not user.is_active:
            raise unauthorized

        return UserRead.model_validate(user)
