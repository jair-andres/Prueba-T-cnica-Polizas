import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.engine import Connection

from ..auth import create_access_token, hash_password, verify_password
from ..config import settings
from ..database import get_connection
from ..repository import UsersRepository
from ..schemas import Token, UserCreate, UserResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _get_conn():
    yield from get_connection()


@router.post("/register", response_model=StandardResponse[UserResponse], status_code=201)
def register(payload: UserCreate, conn: Connection = Depends(_get_conn)):
    """Registra un nuevo usuario. Email y username deben ser únicos."""
    repo = UsersRepository(conn)
    if repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    hashed = hash_password(payload.password)
    user = repo.create(payload.username, payload.email, hashed)
    logger.info("Usuario registrado: username=%s", payload.username)
    return {"status": "success", "data": UserResponse(**user)}


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    conn: Connection = Depends(_get_conn),
):
    """
    Login con username y password.
    - Bloquea la cuenta tras MAX_LOGIN_ATTEMPTS intentos fallidos.
    - El bloqueo dura LOGIN_COOLDOWN_MINUTES minutos.
    """
    repo = UsersRepository(conn)
    user = repo.get_by_username(form.username)

    if user is None:
        # Respuesta genérica para no revelar si el usuario existe
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    now = datetime.now(timezone.utc)

    # Verificar bloqueo por intentos fallidos
    if user["login_attempts"] >= settings.max_login_attempts:
        last = user["last_login_attempt"]
        if last is not None:
            # Asegurar que last sea timezone-aware
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            lockout_end = last + timedelta(minutes=settings.login_cooldown_minutes)
            if now < lockout_end:
                remaining_secs = int((lockout_end - now).total_seconds())
                remaining_min = max(1, remaining_secs // 60)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Cuenta bloqueada temporalmente. Intenta de nuevo en {remaining_min} minuto(s).",
                )
        # Expiró el bloqueo: resetear
        repo.reset_login_attempts(user["id"])
        user["login_attempts"] = 0

    # Verificar contraseña
    if not verify_password(form.password, user["hashed_password"]):
        repo.increment_login_attempts(user["id"], now)
        attempts_after = user["login_attempts"] + 1
        remaining = settings.max_login_attempts - attempts_after
        if remaining <= 0:
            logger.warning("Cuenta bloqueada tras intentos fallidos: username=%s", form.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas. Cuenta bloqueada temporalmente.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenciales incorrectas. Intentos restantes antes del bloqueo: {remaining}",
        )

    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    repo.reset_login_attempts(user["id"])
    token = create_access_token({"sub": user["username"]})
    logger.info("Login exitoso: username=%s", form.username)
    return {"access_token": token, "token_type": "bearer"}
