from sqlalchemy import create_engine, MetaData
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
metadata = MetaData()

def get_connection():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()
