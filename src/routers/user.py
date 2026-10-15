from asyncio import to_thread
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError

from src.auth.passwords import validate_password
from src.auth.utils_jwt import decode_jwt, encode_jwt
from src.db.database import get_session
from src.db.user_crud import create_user, get_user_by_email, get_user_by_id
from src.models.user import LoginRequest, LoginResponse, UserCreate, UserRead

router = APIRouter()


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


@router.post("/auth/login", response_model=LoginResponse)
async def login_user(login_request: LoginRequest):
    async with get_session() as session:
        user = await get_user_by_email(session, login_request.email)
    if user is None or not await to_thread(
        validate_password, login_request.password, user.password_hash
    ):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(401, "Account is inactive")
    payload = {"sub": str(user.id)}
    token = encode_jwt(payload)
    return LoginResponse(access_token=token, token_type="bearer")

@router.get("/me", response_model=UserRead)
async def read_me(credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]):
    token = credentials.credentials
    payload = decode_jwt(token)
    user = await get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(404, "User not found")
    return UserRead
