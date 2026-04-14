-- Icy Barber - TiDB Cloud schema (MySQL-compatible)
-- Ejecuta este script en el SQL Editor de TiDB Cloud.
-- Si ya tienes tablas previas, revisa los DROP con cuidado antes de correrlos.

CREATE DATABASE IF NOT EXISTS icy_barber
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE icy_barber;

-- =========================================================
-- Limpieza opcional (descomenta si quieres recrear desde cero)
-- =========================================================
-- SET FOREIGN_KEY_CHECKS = 0;
-- DROP TABLE IF EXISTS notificaciones_email;
-- DROP TABLE IF EXISTS cita_eventos;
-- DROP TABLE IF EXISTS citas;
-- DROP TABLE IF EXISTS horarios_barbero;
-- DROP TABLE IF EXISTS servicio_barberos;
-- DROP TABLE IF EXISTS servicios;
-- DROP TABLE IF EXISTS clientes;
-- DROP TABLE IF EXISTS usuarios;
-- DROP TABLE IF EXISTS barberos;
-- SET FOREIGN_KEY_CHECKS = 1;

-- =========================================================
-- Barberos
-- =========================================================
CREATE TABLE IF NOT EXISTS barberos (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(120) NOT NULL,
  telefono VARCHAR(30) NULL,
  email VARCHAR(180) NULL,
  instagram_url VARCHAR(255) NULL,
  avatar VARCHAR(255) NOT NULL DEFAULT 'camilo.jpg',
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_barberos_activo (activo),
  UNIQUE KEY uq_barberos_email (email)
);

-- =========================================================
-- Usuarios internos (admin/barbero)
-- role: admin | barbero
-- barbero_id solo aplica cuando role=barbero
-- =========================================================
CREATE TABLE IF NOT EXISTS usuarios (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL,
  barbero_id BIGINT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_usuarios_username (username),
  UNIQUE KEY uq_usuarios_barbero_id (barbero_id),
  INDEX idx_usuarios_role (role),
  CONSTRAINT fk_usuarios_barbero
    FOREIGN KEY (barbero_id) REFERENCES barberos(id)
    ON DELETE SET NULL ON UPDATE CASCADE
);

-- =========================================================
-- Clientes (para reservas)
-- =========================================================
CREATE TABLE IF NOT EXISTS clientes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  nombres VARCHAR(120) NOT NULL,
  apellidos VARCHAR(120) NOT NULL,
  telefono VARCHAR(30) NOT NULL,
  email VARCHAR(180) NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_clientes_email (email),
  INDEX idx_clientes_telefono (telefono)
);

-- =========================================================
-- Servicios
-- pago en efectivo en sucursal
-- =========================================================
CREATE TABLE IF NOT EXISTS servicios (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(150) NOT NULL,
  duracion_minutos INT NOT NULL,
  precio_efectivo INT NOT NULL,
  descripcion TEXT NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_servicios_activo (activo)
);

-- =========================================================
-- Catálogo / Inventario de productos
-- =========================================================
CREATE TABLE IF NOT EXISTS productos_inventario (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  id_item VARCHAR(40) NOT NULL,
  nombre VARCHAR(160) NOT NULL,
  detalles TEXT NULL,
  imagen VARCHAR(255) NULL,
  precio INT NOT NULL DEFAULT 0,
  stock INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_productos_inventario_id_item (id_item),
  INDEX idx_productos_inventario_activo (activo)
);

-- Relación N:M servicios ↔ barberos
CREATE TABLE IF NOT EXISTS servicio_barberos (
  servicio_id BIGINT NOT NULL,
  barbero_id BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (servicio_id, barbero_id),
  CONSTRAINT fk_servicio_barberos_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicios(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_servicio_barberos_barbero
    FOREIGN KEY (barbero_id) REFERENCES barberos(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

-- =========================================================
-- Horarios de trabajo por barbero
-- dia_semana: 1=Lunes ... 7=Domingo
-- =========================================================
CREATE TABLE IF NOT EXISTS horarios_barbero (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barbero_id BIGINT NOT NULL,
  dia_semana TINYINT NOT NULL,
  hora_inicio TIME NOT NULL,
  hora_fin TIME NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_horarios_barbero
    FOREIGN KEY (barbero_id) REFERENCES barberos(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_horarios_barbero_lookup (barbero_id, dia_semana, activo),
  UNIQUE KEY uq_horarios_barbero_slot (barbero_id, dia_semana, hora_inicio, hora_fin)
);

-- =========================================================
-- Citas
-- estado: pendiente | confirmada | completada | cancelada | reagendada
-- =========================================================
CREATE TABLE IF NOT EXISTS citas (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cliente_id BIGINT NOT NULL,
  barbero_id BIGINT NOT NULL,
  servicio_id BIGINT NOT NULL,
  fecha DATE NOT NULL,
  hora_inicio TIME NOT NULL,
  hora_fin TIME NOT NULL,
  estado VARCHAR(30) NOT NULL DEFAULT 'pendiente',
  origen VARCHAR(50) NOT NULL DEFAULT 'Sitio web',
  pagado_efectivo TINYINT(1) NOT NULL DEFAULT 0,
  monto_efectivo INT NULL,
  cancel_token VARCHAR(80) NULL,
  canceled_at TIMESTAMP NULL,
  notas VARCHAR(500) NULL,
  reagendada_desde_cita_id BIGINT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_citas_cliente
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_citas_barbero
    FOREIGN KEY (barbero_id) REFERENCES barberos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_citas_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicios(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_citas_reagendada_desde
    FOREIGN KEY (reagendada_desde_cita_id) REFERENCES citas(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_citas_barbero_fecha (barbero_id, fecha),
  INDEX idx_citas_cliente_fecha (cliente_id, fecha),
  INDEX idx_citas_estado (estado),
  INDEX idx_citas_fecha_hora (fecha, hora_inicio, hora_fin),
  UNIQUE KEY uq_citas_cancel_token (cancel_token)
);

-- =========================================================
-- Historial de eventos sobre citas
-- tipo_evento: creada | confirmada | reagendada | cancelada | eliminada_logica
-- =========================================================
CREATE TABLE IF NOT EXISTS cita_eventos (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cita_id BIGINT NOT NULL,
  tipo_evento VARCHAR(40) NOT NULL,
  actor_usuario_id BIGINT NULL,
  detalle_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_eventos_cita
    FOREIGN KEY (cita_id) REFERENCES citas(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_eventos_actor
    FOREIGN KEY (actor_usuario_id) REFERENCES usuarios(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_eventos_cita (cita_id),
  INDEX idx_eventos_tipo (tipo_evento)
);

-- =========================================================
-- Log de notificaciones por email (SendGrid)
-- tipo_notificacion: confirmacion | confirmacion_barbero | reagendacion | cancelacion | recordatorio_24h
-- estado: pendiente | enviada | error
-- =========================================================
CREATE TABLE IF NOT EXISTS notificaciones_email (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cita_id BIGINT NOT NULL,
  cliente_id BIGINT NOT NULL,
  tipo_notificacion VARCHAR(50) NOT NULL,
  to_email VARCHAR(180) NOT NULL,
  estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
  sendgrid_message_id VARCHAR(120) NULL,
  error_detalle VARCHAR(600) NULL,
  scheduled_for TIMESTAMP NULL,
  sent_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notif_cita
    FOREIGN KEY (cita_id) REFERENCES citas(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_notif_cliente
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_notif_estado (estado),
  INDEX idx_notif_schedule (scheduled_for),
  INDEX idx_notif_tipo (tipo_notificacion)
);

-- =========================================================
-- Portafolio de imágenes
-- barbero_id NULL  = portafolio global
-- barbero_id != NULL = portafolio por barbero
-- =========================================================
CREATE TABLE IF NOT EXISTS portfolio_imagenes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barbero_id BIGINT NULL,
  imagen VARCHAR(255) NOT NULL,
  sort_order INT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_portfolio_scope (barbero_id, activo),
  INDEX idx_portfolio_sort (barbero_id, sort_order)
);

-- =========================================================
-- Datos semilla mínimos
-- =========================================================
INSERT INTO barberos (nombre, telefono, email, avatar)
VALUES
  ('Camilo', '3001112233', 'camilo@icybarber.local', 'camilo.jpg'),
  ('Diego', '3001112244', 'diego@icybarber.local', 'diego.jpg'),
  ('Jaime', '3001112255', 'jaime@icybarber.local', 'jaime.jpg'),
  ('Angel', '3001112266', 'angel@icybarber.local', 'angel.jpg')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO usuarios (username, password_hash, role, barbero_id)
VALUES
  (
    'admin',
    'pbkdf2:sha256:600000$replace$replace_with_hash',
    'admin',
    NULL
  )
ON DUPLICATE KEY UPDATE role = VALUES(role);

INSERT INTO servicios (nombre, duracion_minutos, precio_efectivo, descripcion)
VALUES
  ('Corte de barba', 30, 15000, 'Recorte y diseño de barba.'),
  ('Corte de cabello clásico', 60, 20000, 'Lavado, corte y estilo clásico.'),
  ('Afeitado clásico', 45, 12000, 'Navaja, toalla caliente y bálsamo.'),
  ('Corte y arreglo de bigote', 40, 16000, 'Corte con arreglo de bigote.'),
  ('Lavado, hidratación y corte de barba', 50, 22000, 'Tratamiento completo de barba.')
ON DUPLICATE KEY UPDATE precio_efectivo = VALUES(precio_efectivo);

INSERT INTO productos_inventario (id_item, nombre, detalles, precio, stock, activo)
VALUES
  ('PROD-001', 'Pomada mate clásica', 'Fijación media con acabado natural para peinados diarios.', 28000, 12, 1),
  ('PROD-002', 'Aceite para barba premium', 'Hidratación profunda con aroma suave y textura ligera.', 32000, 8, 1),
  ('PROD-003', 'Shampoo anticaída', 'Limpieza diaria para fortalecer cabello y cuero cabelludo.', 35000, 10, 1)
ON DUPLICATE KEY UPDATE
  nombre = VALUES(nombre),
  detalles = VALUES(detalles),
  precio = VALUES(precio),
  stock = VALUES(stock),
  activo = VALUES(activo);

-- Asignar todos los servicios a todos los barberos (seed inicial)
INSERT IGNORE INTO servicio_barberos (servicio_id, barbero_id)
SELECT s.id, b.id
FROM servicios s
CROSS JOIN barberos b;

-- Horario base Lunes a Viernes de 09:00 a 18:00 para todos
INSERT IGNORE INTO horarios_barbero (barbero_id, dia_semana, hora_inicio, hora_fin)
SELECT b.id, d.dia_semana, '09:00:00', '18:00:00'
FROM barberos b
JOIN (
  SELECT 1 AS dia_semana UNION ALL
  SELECT 2 UNION ALL
  SELECT 3 UNION ALL
  SELECT 4 UNION ALL
  SELECT 5
) d;

-- =========================================================
-- Nota de negocio importante:
-- El bloqueo de cruces de citas (overlap) se valida en backend/transacción,
-- porque no se puede garantizar con un UNIQUE simple sobre rangos de tiempo.
-- =========================================================
