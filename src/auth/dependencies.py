from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from src.auth.utils_jwt import decode_jwt
from src.db.database import get_session
from src.db.user_crud import get_user_by_id
from src.models.user import UserRead

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer)
    ],
) -> UserRead:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_jwt(credentials.credentials)
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    async with get_session() as session:
        user = await get_user_by_id(session, user_id)

        if user is None or not user.is_active:
            raise unauthorized

        return UserRead.model_validate(user)