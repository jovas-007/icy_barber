# Icy Barber

> Sistema de reservaciones para barbería con acceso por roles (admin/barbero).

Descripción
- Aplicación Flask con vista pública para clientes y autenticación para usuarios internos.
- La página principal (`/`) sigue siendo para clientes.
- El logo izquierdo en la home redirige al login interno.
- Soporta SQLite local y TiDB Cloud por `DATABASE_URL` o variables `DB_*`.

Rutas principales
- `/` : Página pública de reservas.
- `/login` : Login interno (admin/barbero).
- `/logout` : Cerrar sesión.
- `/admin` : Panel agenda (solo admin).
- `/barbero` : Panel agenda del barbero logueado (solo barbero).
- `/api/barberos` : JSON de barberos activos.
- `/api/servicios` : JSON de servicios.
- `/api/citas` : JSON de citas (admin ve todas, barbero solo las suyas).
- `/api/citas/public` : Crear cita desde la web pública (cliente).
- `/api/admin/barberos` : Listar/crear barberos (admin).
- `/api/admin/barberos/<id>` : Editar/desactivar barbero (admin).

Funcionalidad ya implementada
- Formulario real de cita en home con campos: nombres, apellidos, teléfono, correo, servicio, barbero, fecha y hora.
- Validación backend para bloquear:
  - citas fuera de horario laboral del barbero,
  - cruces de horario con citas existentes,
  - asignación de barbero a servicios no compatibles.
- CRUD de barberos desde dashboard admin:
  - crear barbero,
  - editar datos y horario,
  - desactivar barbero.

Credenciales demo iniciales
- Admin:
  - usuario: `admin`
  - contraseña: `admin123`
- Barbero:
  - usuario: `barbero1` (también `barbero2`, `barbero3`, `barbero4`)
  - contraseña temporal: `temp123`

Estructura relevante
- Archivo principal: [app.py](app.py)
- Plantillas: [templates/base.html](templates/base.html), [templates/booking.html](templates/booking.html), [templates/dashboard.html](templates/dashboard.html), [templates/login.html](templates/login.html)
- Estilos y assets: `static/css/` y `static/img/`
- Base local generada automáticamente al arrancar: `instance/icy_barber.db`
- Script de esquema TiDB: [sql/tidb_schema.sql](sql/tidb_schema.sql)
- Variables ejemplo: [.env.example](.env.example)

Configuración TiDB Cloud
1. Ejecutar el esquema en TiDB SQL Editor:

```sql
-- copiar y ejecutar completo
sql/tidb_schema.sql
```

2. Crear `.env` desde `.env.example` y configurar:

```env
SECRET_KEY=tu_secret
ADMIN_PASSWORD=tu_password_admin_real
DB_HOST=...
DB_PORT=4000
DB_USERNAME=...
DB_PASSWORD=...
DB_DATABASE=icy_barber
AUTO_BOOTSTRAP_DB=false
```

3. Alternativa recomendada: usar solo `DATABASE_URL`:

```env
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:4000/icy_barber?charset=utf8mb4&ssl_verify_cert=true&ssl_verify_identity=true
```

Nota: con TiDB (`AUTO_BOOTSTRAP_DB=false`) la app no crea tablas automáticamente; usa el script SQL.

Cómo ejecutar (Windows, PowerShell)
1. Activar el entorno virtual:

```powershell
& C:\Users\jovas\Music\icy_barber\venv\Scripts\Activate.ps1
```

2. Instalar dependencias (si no lo hiciste):

```powershell
pip install -r requirements.txt
```

3. Ejecutar la aplicación (usar el Python del venv):

```powershell
python app.py
# o (ruta explícita)
c:/Users/jovas/Music/icy_barber/venv/Scripts/python.exe app.py
```

4. Abrir en navegador:

```text
http://127.0.0.1:8000/
```

Observación: en mi intento de iniciar el servidor apareció este error:

```
Intento de acceso a un socket no permitido por sus permisos de acceso
```

Posibles soluciones si ves ese error
- Ejecutar PowerShell como Administrador y volver a intentar.
- Permitir `python.exe` a través del Firewall de Windows o desactivar temporalmente el antivirus que pueda bloquear sockets.
- Probar con otro puerto (por ejemplo `port=8000`) editando `app.py` o ejecutando:

```powershell
python -c "import app as _app; _app.app.run(debug=False, port=8000)"
```
- Ejecutar dentro de WSL (si está disponible) para evitar políticas locales de Windows.

Descripción técnica rápida
- `app.py` ahora usa:
  - `Flask-SQLAlchemy` para modelos persistentes (`User`, `Barbero`, `Cliente`, `Servicio`, `Cita`, `HorarioBarbero`).
  - `Flask-Login` para sesión por roles (admin/barbero).
- En SQLite local se crean tablas y datos semilla automáticamente.
- En TiDB Cloud se usa esquema SQL pre-creado y la contraseña admin se puede fijar con `ADMIN_PASSWORD`.
- `booking.html` se mantiene como frontend público para clientes.

Siguientes pasos sugeridos
- Integrar formulario real de reserva cliente con: nombre, apellidos, teléfono y correo.
- Implementar CRUD de barberos (admin) y acciones de citas para barbero (confirmar/completar/cancelar).
- Integrar SendGrid para notificaciones y pasar variables como secrets en Railway.

---
Generado automáticamente: descripción y pasos básicos para ejecutar la app.
