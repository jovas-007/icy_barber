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

### **PASO 7: Imágenes de Portfolio (IMPORTANTE)**

Tu app guarda imágenes en `static/img/portfolio` (filesystem local).

**En Railway esto es efímero**, se perderán en redeploy.

**Opciones:**
- **Opción A (Temporal, para testing)**: No hacer nada, las imágenes se pierden en redeploy
- **Opción B (Recomendado)**: Agregar Volume persistente en Railway
  - En **Settings** del servicio → **Generate** un Volume (mínimo 1GB)
  - Monta en `/app/static/img/portfolio`
  - Las imágenes persistirán entre redeploys
- **Opción C (Producción real)**: Usar S3 / Cloudinary / R2 - por ahora no lo configuramos

---

## 🔍 Si Algo Falla

### Error: "ERROR: Failed to load DATABASE_URL"
- Revisa que `DATABASE_URL` esté exacta con credenciales correctas
- Revisa que MySQL esté corriendo (tab del servicio MySQL debe estar verde)

### Error: "port is already in use"
- No es problema tuyo, Railway maneja el puerto automáticamente

### Imágenes no aparecen después de redeploy
- Agrégales Volume persistente (Paso 8, Opción B)

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
| 7 | (Opcional) Agregar Volume para imágenes persistentes |

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
