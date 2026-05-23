from sqlalchemy import create_engine, MetaData
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
metadata = MetaData()

def get_connection():
    """Provee una conexión con transacción automática.
    Al salir del contexto se hace commit (o rollback si hay error)."""
    with engine.begin() as conn:
        yield conn