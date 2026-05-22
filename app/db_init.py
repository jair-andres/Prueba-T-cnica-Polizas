from app.database import engine
from app.models import metadata


def init_db() -> None:
    print("Creando tablas en la base de datos...")
    metadata.create_all(engine)
    print("Tablas creadas correctamente.")


if __name__ == "__main__":
    init_db()
