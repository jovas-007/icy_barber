# 🚀 Pasos para Desplegar en Railway

Este archivo contiene los pasos exactos y el orden correcto para desplegar **Icy Barber** en Railway.

## ✅ Checklist Pre-Deployment (Ya Completado)

- [x] `gunicorn==22.0.0` agregado a requirements.txt
- [x] `Procfile` creado con comando web
- [x] `.env.example` con variables de entorno documentadas
- [x] App soporta `DATABASE_URL` y `SERVER_NAME`

---

## 📋 Pasos en Railway (Orden Exacto)

### **PASO 1: Crear Proyecto en Railway**

1. Ve a [railway.app](https://railway.app)
2. Loguéate o crea cuenta
3. Click en **New Project** → **Deploy from GitHub**
4. Conecta tu repo de GitHub
5. Selecciona el repositorio `icy_barber`
6. Railway debe detectar automáticamente que es una app Python

### **PASO 2: Configurar Servicio Principal (Web Server)**

Una vez importado:

1. Vas a **Settings** del servicio (debe mostrar `icy_barber`)
2. Verifica:
   - **Root Directory**: déjalo en blanco (está en raíz)
   - **Start Command**: debe decir `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
     - Si no está, ve a **Variables** y que Railway lo detecte automáticamente
   - La rama (Branch): asegúrate de que está en `main` o tu rama principal

### **PASO 3: Configurar Variables de Entorno**

En el servicio **web** (tu app), ve a **Variables** y agrega estas:

| Variable | Valor | Notas |
|----------|-------|-------|
| `DATABASE_URL` | `mysql+pymysql://4PzpG5TWKzJQU8p.root:<PASSWORD>@gateway01.us-west-2.prod.aws.tidbcloud.com:4000/icy_barber` | Reemplaza `<PASSWORD>` con tu contraseña de TiDB |
| `SECRET_KEY` | Clave aleatoria de min. 32 caracteres | Usa: `python -c "import secrets; print(secrets.token_urlsafe(32))"` localmente |
| `ADMIN_PASSWORD` | Tu contraseña fuerte para admin | Min. 8 caracteres, números + mayúsculas |
| `AUTO_BOOTSTRAP_DB` | `true` | **SOLO en primer deploy** para crear tablas |
| `SERVER_NAME` | `icybarber.up.railway.app` | Railway te da el dominio exacto; úsalo sin `https://` |

### **PASO 5: Primer Deploy**

1. Una vez configuradas las variables, Railway debe detectar cambios en el repo
2. O fuerza un deploy: click en **Deploy** en la interfaz
3. **Monitorea los logs** en el tab **Deployments**:
   - Espera4a que veas `Application started on http://0.0.0.0:PORT`
   - Si hay error de DB, revisa que `DATABASE_URL` esté bien
4. El app debe crearse la estructura de tablas automáticamente (porque `AUTO_BOOTSTRAP_DB=true`)

### **PASO 5: Verificar Deploy**

1. Una vez en el tab **Deployments**, obtendrás la URL pública (`https://icybarber.up.railway.app`)
2. Abre esa URL en el navegador
3. Deberías ver la página de login

### **PASO 6: Cambiar `AUTO_BOOTSTRAP_DB` a `false`** ⚠️

Una vez que el app arrancó correctamente la PRIMERA VEZ:

1. Ve a **Variables** del servicio web
2. Cambia `AUTO_BOOTSTRAP_DB` de `true` a `false`
3. Haz que trigger un nuevo deploy (o simplemente commit&push a GitHub)
4. Esto evita que se recreen las tablas en redeploys posteriores

### **PASO 7: Imágenes persistentes (Catálogo + Portafolio)**

Tu app guarda imágenes en:

- `static/img/uploads` (avatares + catálogo)
- `static/img/portfolio` (portafolio global y por barbero)

**En Railway esto es efímero**, se perderán en redeploy si no hay volumen.

Configuración recomendada (la de tu screenshot):

1. Crear 1 volume en el servicio web
2. Mount path: `/data/media`
3. Agregar variable en Railway:
   - `PERSISTENT_MEDIA_ROOT=/data/media`
4. Hacer redeploy

Notas importantes:

- Railway permite **un solo volume por servicio**.
- La app guarda `uploads` y `portfolio` en el volume y los sirve por `/media/...`.
- Si las imágenes ya se perdieron en un deploy anterior, debes volver a subirlas (no se recuperan solas).

---

## 🔍 Si Algo Falla

### Error: "ERROR: Failed to load DATABASE_URL"
- Revisa que `DATABASE_URL` esté exacta con credenciales correctas
- Revisa que MySQL esté corriendo (tab del servicio MySQL debe estar verde)

### Error: "port is already in use"
- No es problema tuyo, Railway maneja el puerto automáticamente

### Imágenes no aparecen después de redeploy
- Verifica que exista volume montado en `/data/media`
- Verifica variable `PERSISTENT_MEDIA_ROOT=/data/media`
- Re-sube imágenes faltantes desde dashboard (catálogo y portafolio)

### Logs muestran "Connection refused"
- Espera a que MySQL esté totalmente listo (30-60 seg)
- Railway automáticamente reinicia si DB está lista

---

## 📝 Resumen Rápido

| Paso | Qué Hacer |
|------|-----------|
| 1 | Conectar GitHub a Railway |
| 2 | Verificar que tome `Procfile` automáticamente |
| 3 | Configurar 5 variables de entorno (DATABASE_URL de TiDB, SECRET_KEY, ADMIN_PASSWORD, AUTO_BOOTSTRAP_DB, SERVER_NAME) |
| 4 | Primer deploy automático (o fuerza uno) |
| 5 | Verificar que conexión a TiDB funcione en los logs |
| 6 | Si todo OK, cambiar `AUTO_BOOTSTRAP_DB=false` |
| 7 | Configurar volume en `/data/media` + `PERSISTENT_MEDIA_ROOT` |

---

## 🎯 Test Final

Una vez deployado:

```bash
# Desde tu local, en terminal:
curl https://icybarber.up.railway.app/
# Deberías ver HTML de la página de login
```

Si necesitas DEBUG, en Railway puedes ver logs en la sección **Deployments** → **Logs**.

---

**Estás list@ para Railway. 🚀**
