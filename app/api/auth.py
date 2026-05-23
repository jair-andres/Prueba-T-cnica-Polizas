import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ..auth import create_access_token, hash_password, verify_password
from ..config import settings
from ..database import get_connection
from ..repository import UsersRepository
from ..schemas import StandardResponse, Token, UserCreate, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticación"])

_401 = {401: {"description": "Credenciales incorrectas", "content": {"application/json": {"example": {"status": "error", "message": "Credenciales incorrectas"}}}}}
_429 = {429: {"description": "Cuenta bloqueada por exceso de intentos fallidos", "content": {"application/json": {"example": {"status": "error", "message": "Cuenta bloqueada temporalmente. Intenta de nuevo en 15 minuto(s)."}}}}}
_400 = {400: {"description": "Datos duplicados o inválidos", "content": {"application/json": {"example": {"status": "error", "message": "El nombre de usuario ya existe"}}}}}


def _get_conn():
    yield from get_connection()


@router.post(
    "/register",
    response_model=StandardResponse[UserResponse],
    status_code=201,
    summary="Registrar nuevo usuario",
    responses={**_400},
    description="""
Crea un usuario con username, email y contraseña.

**Requisitos de contraseña:** mínimo 8 caracteres, máximo 72.

**Restricciones:** `username` y `email` deben ser únicos en el sistema.
""",
)
def register(payload: UserCreate, conn: Connection = Depends(_get_conn)):
    repo = UsersRepository(conn)
    if repo.get_by_username(payload.username):
        raise HTTPException(400, "El nombre de usuario ya existe")
    if repo.get_by_email(payload.email):
        raise HTTPException(400, "El correo ya está registrado")
    try:
        user = repo.create(payload.username, payload.email, hash_password(payload.password))
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
        if "username" in constraint:
            raise HTTPException(409, "El nombre de usuario ya existe")
        if "email" in constraint:
            raise HTTPException(409, "El correo ya está registrado")
        raise HTTPException(409, "El usuario ya existe")
    logger.info("Usuario registrado: %s", payload.username)
    return {"status": "success", "data": UserResponse(**user)}


@router.post(
    "/login",
    response_model=Token,
    summary="Obtener token JWT",
    responses={**_401, **_429},
    description="""
Autentica con **username** y **password** (`application/x-www-form-urlencoded`).

Devuelve un `access_token` de tipo Bearer:
```
Authorization: Bearer <token>
```

**Cómo usarlo en Swagger UI:**
1. Clic en **Authorize 🔒** (arriba a la derecha).
2. Escribe `username` y `password`.
3. `client_id` y `client_secret` déjalos vacíos — esta API no los usa.
4. Clic en **Authorize** → el token se guarda automáticamente.

**Reglas de bloqueo:** tras 5 intentos fallidos la cuenta se bloquea 15 minutos.
""",
)
def login(form: OAuth2PasswordRequestForm = Depends(), conn: Connection = Depends(_get_conn)):
    repo = UsersRepository(conn)
    user = repo.get_by_username(form.username)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")

    now = datetime.now(timezone.utc)

    if user["login_attempts"] >= settings.max_login_attempts:
        last = user["last_login_attempt"]
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            lockout_end = last + timedelta(minutes=settings.login_cooldown_minutes)
            if now < lockout_end:
                mins = max(1, int((lockout_end - now).total_seconds()) // 60)
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Cuenta bloqueada. Intenta en {mins} minuto(s).")
        repo.reset_login_attempts(user["id"])
        user["login_attempts"] = 0

    if not verify_password(form.password, user["hashed_password"]):
        repo.increment_login_attempts(user["id"], now)
        remaining = settings.max_login_attempts - (user["login_attempts"] + 1)
        if remaining <= 0:
            logger.warning("Cuenta bloqueada: %s", form.username)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas. Cuenta bloqueada temporalmente.")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Credenciales incorrectas. Intentos restantes: {remaining}")

    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo")

    repo.reset_login_attempts(user["id"])
    logger.info("Login exitoso: %s", form.username)
    return {"access_token": create_access_token({"sub": user["username"]}), "token_type": "bearer"}
