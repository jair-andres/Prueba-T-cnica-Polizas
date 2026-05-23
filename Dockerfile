FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar salida estándar sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# postgresql-client para pg_isready en el entrypoint; tzdata para ZoneInfo en Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client tzdata && \
    rm -rf /var/lib/apt/lists/*

# Crear un usuario y grupo sin privilegios de root (Regla: app NO debe correr como root)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Dar permisos de ejecución al entrypoint
RUN chmod +x entrypoint.sh

# Cambiar la propiedad de los archivos al usuario no root
RUN chown -R appuser:appgroup /app

# Cambiar al usuario no root
USER appuser

EXPOSE 8000

# Usar entrypoint script que espera por DB e inicializa tablas
ENTRYPOINT ["./entrypoint.sh"]