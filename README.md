# Sistema de Gestión de Pólizas

## 1. Descripción

API REST para el MVP de un sistema de pólizas con cobros recurrentes. Permite registrar clientes, emitir pólizas con beneficiarios, registrar pagos parciales o totales y consultar el estado de cartera.

## 2. Tecnologías

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI |
| Base de datos | PostgreSQL 16 |
| ORM / DB | SQLAlchemy 2 + psycopg2 |
| Autenticación | JWT (python-jose + bcrypt) |
| Tests | Pytest + FastAPI TestClient |
| Infraestructura | Docker + docker-compose |

## 3. Ejecución

```bash
# Copiar variables de entorno
cp env.example .env

# Levantar todo el stack
docker-compose up --build -d

# Documentación interactiva
http://localhost:8000/docs
```

La base de datos se inicializa automáticamente al arrancar. No requiere pasos adicionales.

**Endpoints disponibles:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Registrar usuario |
| POST | `/auth/login` | Obtener token JWT |
| POST | `/clientes` | Crear cliente |
| POST | `/polizas` | Crear póliza con beneficiarios |
| POST | `/polizas/{id}/pagos` | Registrar pago |
| GET | `/polizas/{id}/estado` | Consultar estado y saldo |
| GET | `/reportes/cartera-vencida` | Pólizas con mora > 30 días |

Todos los endpoints de negocio requieren `Authorization: Bearer <token>`. En Swagger (`/docs`) usar el botón **Authorize 🔒**.

## 4. Tests

```bash
docker-compose exec app python -m pytest tests/ -v
```

Los tests usan rollback por transacción: la base de datos queda intacta después de ejecutarlos.

| Test | Qué valida |
|------|-----------|
| `test_pago_idempotente` | La misma `clave_idempotencia` no duplica el pago |
| `test_estado_poliza_mora_y_al_dia` | Lógica de mora con zona horaria Bogotá |
| `test_reporte_cartera_vencida` | Pólizas en mora aparecen; las pagadas no |

## 5. Modelo de datos

```
clientes          → id, nombre, documento (único), email
polizas           → id, numero_poliza (único), cliente_id, prima_total,
                    fecha_emision, fecha_vencimiento, estado
beneficiarios     → id, nombre, documento (único)
poliza_beneficiarios → poliza_id + beneficiario_id (relación N:M)
pagos             → id, poliza_id, monto, fecha_pago, clave_idempotencia
users             → id, username, email, hashed_password, login_attempts
```

Un cliente puede tener múltiples pólizas. Una póliza puede tener múltiples beneficiarios. Un beneficiario (identificado por documento) puede estar en pólizas de distintos clientes.

## 6. Decisiones de diseño y supuestos

**Idempotencia en pagos:** `clave_idempotencia` con constraint `UNIQUE(poliza_id, clave_idempotencia)` + doble verificación antes y después del lock. Un reintento con la misma clave devuelve el pago original sin duplicarlo.

**Concurrencia:** `SELECT FOR UPDATE` con `lock_timeout = 5s` serializa pagos simultáneos sobre la misma póliza. Si el lock no se obtiene en 5 segundos, se devuelve 503 en lugar de bloquear indefinidamente.

**Estado de póliza:** Se calcula en cada consulta con la fecha actual en `America/Bogota`. Tres estados: `al día` (prima cubierta), `en mora` (vencida con saldo pendiente), `pendiente` (vigente con saldo).

**Supuesto:** El campo `estado` en la tabla `polizas` no cambia automáticamente al vencerse — eso es responsabilidad de un proceso externo. La API calcula el estado real dinámicamente.

**Supuesto:** Un pago no puede exceder el saldo pendiente. Los sobrepagos se rechazan con 400.

**Supuesto:** `"último año"` en el reporte Q3 de queries.sql se interpreta como los últimos 365 días (ventana rodante), no el año calendario, por ser más útil operativamente.

---

## Code Review — legacy.py

Análisis del código heredado en `code_review/legacy.py`. Problemas ordenados de mayor a menor riesgo.

### 🔴 1. SQL Injection — Riesgo crítico

**Problema:** Consultas construidas concatenando strings con datos del usuario:
```python
query = "SELECT id FROM polizas WHERE id = " + str(poliza_id)
insert = f"INSERT INTO pagos VALUES ({poliza_id}, {monto}, '{referencia}')"
```
Un atacante puede enviar `1; DROP TABLE pagos;--` y destruir la base de datos.

**Solución:** Usar parámetros siempre:
```python
cur.execute("SELECT id FROM polizas WHERE id = %s", (poliza_id,))
```

---

### 🔴 2. Credenciales hardcodeadas — Riesgo crítico

**Problema:**
```python
DB_PASS = "Tr4nsf2023!"
```
La contraseña de producción está en el código. Cualquiera con acceso al repo accede a la base de datos. Si el historial de git estuvo público en algún momento, la contraseña está expuesta permanentemente.

**Solución:**
```python
DB_PASS = os.getenv("DB_PASSWORD")
```

---

### 🔴 3. Error silenciado con schema incorrecto — Riesgo crítico

**Problema:** `beneficiarios` no tiene columna `poliza_id`, por lo que la consulta siempre falla. El error se oculta devolviendo 200:
```python
except Exception as e:
    return jsonify({"ok": True}), 200  # ← el endpoint nunca funciona
```

**Solución:** Corregir el join y no silenciar excepciones:
```python
cur.execute("""
    SELECT b.id, b.nombre, b.documento
    FROM beneficiarios b
    JOIN poliza_beneficiarios pb ON pb.beneficiario_id = b.id
    WHERE pb.poliza_id = %s
""", (poliza_id,))
```

---

### 🟠 4. Conexiones sin cerrar — Riesgo alto

**Problema:** Cada request abre una conexión nueva sin cerrarla. Bajo carga PostgreSQL se queda sin conexiones disponibles y el servicio cae.

**Solución:** Context manager o pool de conexiones:
```python
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(...)
```

---

### 🟠 5. Race condition en pagos — Riesgo alto

**Problema:** Entre el INSERT del pago y el cálculo del saldo, otro request puede insertar simultáneamente. Dos requests pueden exceder la prima total.

**Solución:** `SELECT FOR UPDATE` sobre la póliza antes de insertar. Solo un pago a la vez puede procesarse por póliza.

---

### 🟡 6. N+1 queries — Riesgo medio

**Problema:** Una query por cada póliza del cliente:
```python
for p in polizas:
    cur.execute("SELECT SUM(monto) FROM pagos WHERE poliza_id = " + str(p[0]))
```

**Solución:** Una sola query con JOIN:
```python
cur.execute("""
    SELECT pol.id, COALESCE(SUM(p.monto), 0)
    FROM polizas pol LEFT JOIN pagos p ON p.poliza_id = pol.id
    WHERE pol.cliente_id = %s GROUP BY pol.id
""", (cliente_id,))
```

---

### 🟡 7. `debug=True` en producción — Riesgo medio

**Problema:** Expone el debugger interactivo. Un atacante puede ejecutar código Python arbitrario en el servidor.

**Solución:** `app.run(debug=os.getenv("APP_ENV") == "development")`

---

### 🟡 8. Sin validación de entrada — Riesgo medio

`monto` y `poliza_id` se usan sin validar tipo ni rango. Si llegan como `null` o negativos, el INSERT falla o inserta datos incorrectos.

---

### 🟡 9. `datetime.now()` sin zona horaria — Riesgo medio

Devuelve la hora local del servidor. Si el servidor cambia de zona, los timestamps históricos quedan inconsistentes. Usar `datetime.now(timezone.utc)`.

---

### ✅ Lo que está bien

- Separación en funciones por endpoint (estructura correcta).
- `data.get("referencia", "")` evita KeyError con valor por defecto.
- Verificación de existencia de la póliza antes de insertar el pago (404 correcto).

---

## Cómo trabajé este reto

Usé Claude (Anthropic) como asistente durante el desarrollo para revisar decisiones de diseño, detectar race conditions y depurar configuración de Docker. La lógica de negocio, arquitectura y decisiones son propias. Puedo defender cada parte del código en la entrevista.

---

## Si tuviera 4 horas más

Dejaría fuera mejoras al reporte de cartera vencida y priorizaría:

1. **Proceso de cierre de pólizas:** hoy el estado `en mora` se calcula dinámicamente en cada consulta pero el campo `estado` en la tabla nunca cambia. Un proceso batch que actualice ese campo daría consistencia real y simplificaría las consultas de reporte.

2. **Test de concurrencia:** el caso más crítico — dos pagos simultáneos sobre la misma póliza — está manejado en código con `FOR UPDATE` pero no tiene prueba automatizada que lo valide.

Agregar features sin cubrir estos dos puntos sería construir sobre base inestable.
