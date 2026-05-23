-- =============================================================================
-- queries.sql — Consultas analíticas del sistema de pólizas
-- Base de datos: PostgreSQL 16
-- Zona horaria de negocio: America/Bogota (UTC-5)
-- Los timestamps se almacenan en UTC; las comparaciones de fechas de negocio
-- se convierten explícitamente a America/Bogota donde corresponde.
-- =============================================================================


-- =============================================================================
-- Q1: Clientes que NO han realizado pagos en los últimos 60 días
-- =============================================================================
--
-- DETALLE DETECTADO:
--   La tabla pagos NO tiene cliente_id. El vínculo es pagos → polizas → clientes.
--   Una lectura rápida del enunciado lleva a buscar cliente_id en pagos, que no existe.
--   Se debe atravesar polizas para llegar al cliente.
--
--   Segundo detalle: se usa NOT EXISTS en lugar de NOT IN porque:
--   a) NOT IN con una subconsulta que devuelve NULLs retorna 0 filas (trampa SQL clásica).
--   b) NOT EXISTS usa semi-join y se detiene en el primer match → más eficiente.
--
--   Tercer detalle: "no han realizado pagos en los últimos 60 días" incluye clientes
--   que NUNCA han pagado, no solo los que dejaron de pagar recientemente.
--   NOT EXISTS cubre ambos casos de forma natural.
--
--   Los 60 días se evalúan en UTC porque fecha_pago es TIMESTAMP WITH TIME ZONE.
--   La diferencia con Bogotá (UTC-5) es de máximo 5 horas, irrelevante para un
--   umbral de 60 días, por lo que no se convierte la zona horaria aquí.

SELECT
    c.id        AS cliente_id,
    c.nombre,
    c.documento,
    c.email
FROM clientes c
WHERE NOT EXISTS (
    SELECT 1
    FROM pagos     p
    JOIN polizas pol ON pol.id = p.poliza_id
    WHERE pol.cliente_id = c.id
      AND p.fecha_pago >= NOW() - INTERVAL '60 days'
)
ORDER BY c.nombre;


-- =============================================================================
-- Q2: Resumen de pólizas activas: prima, pagado, saldo y beneficiarios
-- =============================================================================
--
-- DETALLE DETECTADO:
--   Sin COALESCE en SUM(p.monto), las pólizas activas sin ningún pago devuelven
--   NULL en total_pagado y NULL en saldo_pendiente, en lugar de 0 y prima_total.
--   LEFT JOIN es obligatorio en pagos y en poliza_beneficiarios para incluir
--   pólizas sin pagos ni beneficiarios asociados aún.
--
--   Segundo detalle: COUNT(DISTINCT pb.beneficiario_id) en lugar de COUNT(pb.*)
--   porque el JOIN con pagos multiplica las filas de poliza_beneficiarios por cada
--   pago existente. Sin DISTINCT el conteo de beneficiarios quedaría inflado.
--
--   Supuesto documentado: "activa" es el valor literal en polizas.estado.
--   Pólizas vencidas por fecha pero con estado='activa' siguen apareciendo aquí;
--   el cambio de estado es responsabilidad de un proceso de negocio separado.

SELECT
    pol.id                                          AS poliza_id,
    pol.numero_poliza,
    c.nombre                                        AS cliente_nombre,
    pol.prima_total,
    COALESCE(SUM(p.monto), 0)                       AS total_pagado,
    pol.prima_total - COALESCE(SUM(p.monto), 0)     AS saldo_pendiente,
    COUNT(DISTINCT pb.beneficiario_id)              AS cantidad_beneficiarios
FROM polizas pol
JOIN  clientes             c  ON c.id  = pol.cliente_id
LEFT JOIN pagos            p  ON p.poliza_id  = pol.id
LEFT JOIN poliza_beneficiarios pb ON pb.poliza_id = pol.id
WHERE pol.estado = 'activa'
GROUP BY
    pol.id,
    pol.numero_poliza,
    c.nombre,
    pol.prima_total
ORDER BY pol.id;


-- =============================================================================
-- Q3: Top 5 clientes con mayor monto pagado acumulado en el último año
-- =============================================================================
--
-- DETALLE DETECTADO:
--   "Último año" es ambiguo: puede ser el año calendario (1 ene – 31 dic) o los
--   últimos 365 días rodantes desde hoy. Se elige la ventana rodante de 12 meses
--   porque es más útil operativamente y no depende de la fecha de ejecución de la
--   consulta dentro del año. Si el negocio requiere año calendario, cambiar el
--   WHERE por: DATE_TRUNC('year', p.fecha_pago AT TIME ZONE 'America/Bogota')
--             = DATE_TRUNC('year', NOW() AT TIME ZONE 'America/Bogota')
--
--   Segundo detalle: se incluyen pagos sobre pólizas en cualquier estado porque
--   el monto ya fue recibido y es histórico. Filtrar solo pólizas 'activa' reduciría
--   el ranking si un cliente tiene pólizas vencidas con pagos recientes.
--
--   Tercer detalle: LIMIT 5 sin manejo de empates. Si dos clientes tienen el mismo
--   total, el orden entre ellos lo decide el motor (no determinístico). Para producción
--   se agregaría un desempate: ORDER BY total_pagado_anio DESC, c.id ASC.
--   Se documenta el supuesto en lugar de añadir complejidad no pedida.

SELECT
    c.id                    AS cliente_id,
    c.nombre,
    c.documento,
    SUM(p.monto)            AS total_pagado_anio
FROM clientes  c
JOIN polizas   pol ON pol.cliente_id = c.id
JOIN pagos     p   ON p.poliza_id   = pol.id
WHERE p.fecha_pago >= NOW() - INTERVAL '1 year'
GROUP BY
    c.id,
    c.nombre,
    c.documento
ORDER BY total_pagado_anio DESC
LIMIT 5;
