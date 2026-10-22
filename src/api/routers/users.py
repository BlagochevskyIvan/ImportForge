from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import get_current_user, require_auth_origin
from src.auth.jwt import encode_jwt
from src.auth.passwords import validate_password
from src.auth.refresh import generate_refresh_token, hash_refresh_token
from src.core.config import REFRESH_COOKIE_SECURE, REFRESH_TOKEN_EXPIRATION_DAYS
from src.db import refresh_crud
from src.db.database import get_session
from src.db.user_crud import create_user, get_user_by_email
from src.schemas.users import LoginRequest, LoginResponse, UserCreate, UserRead

router = APIRouter()


def token_response(response: Response, access_token: str, refresh_token: str) -> LoginResponse:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRATION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return LoginResponse(access_token=access_token, token_type="bearer")


@router.post("/auth/register", response_model=UserRead, status_code=201)
async def register_user(user: UserCreate):
    try:
        async with get_session() as session, session.begin():
            created_user = await create_user(session, user)
            result = UserRead.model_validate(created_user)
        return result
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Username or email already exists") from exc
        raise


@router.post(
    "/auth/login", response_model=LoginResponse, dependencies=[Depends(require_auth_origin)]
)
async def login_user(login_request: LoginRequest, response: Response):
    async with get_session() as session, session.begin():
        user = await get_user_by_email(session, login_request.email)
        if user is None or not await to_thread(
            validate_password, login_request.password, user.password_hash
        ):
            raise HTTPException(401, "Invalid email or password")
        if not user.is_active:
            raise HTTPException(401, "Account is inactive")
        token = encode_jwt({"sub": str(user.id)})
        refresh_token = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRATION_DAYS)
        saved = await refresh_crud.save_refresh_token(
            session, user.id, hash_refresh_token(refresh_token), expires_at
        )
        if not saved:
            raise HTTPException(401, "Account is inactive")
    return token_response(response, token, refresh_token)


@router.post(
    "/auth/refresh", response_model=LoginResponse, dependencies=[Depends(require_auth_origin)]
)
async def refresh_user(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    unauthorized = HTTPException(
        401, "Invalid or expired refresh token", headers={"Cache-Control": "no-store"}
    )
    if not refresh_token:
        raise unauthorized
    new_refresh_token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRATION_DAYS)
    async with get_session() as session, session.begin():
        user_id = await refresh_crud.rotate_refresh_token(
            session,
            hash_refresh_token(refresh_token),
            hash_refresh_token(new_refresh_token),
            expires_at,
        )
        if user_id is None:
            raise unauthorized
        token = encode_jwt({"sub": str(user_id)})
    return token_response(response, token, new_refresh_token)


@router.post("/auth/logout", status_code=204, dependencies=[Depends(require_auth_origin)])
async def logout_user(
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        async with get_session() as session, session.begin():
            await refresh_crud.revoke_refresh_token(session, hash_refresh_token(refresh_token))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        "refresh_token", path="/", httponly=True, secure=REFRESH_COOKIE_SECURE, samesite="lax"
    )
    return response


@router.get("/me", response_model=UserRead)
async def read_me(current_user: Annotated[UserRead, Depends(get_current_user)]):
    return current_user
