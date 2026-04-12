import os
import re
import json
import smtplib
import ssl
from email.message import EmailMessage
from html import escape as html_escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from PIL import Image, ImageOps
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()


def normalize_database_uri(uri):
    if uri.startswith("mysql://"):
        return "mysql+pymysql://" + uri[len("mysql://") :]
    return uri


def build_database_uri():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        return normalize_database_uri(db_url)

    db_host = os.getenv("DB_HOST", "").strip()
    db_user = os.getenv("DB_USERNAME", "").strip()
    db_password = os.getenv("DB_PASSWORD", "").strip()
    db_name = os.getenv("DB_DATABASE", "").strip()
    db_port = os.getenv("DB_PORT", "4000").strip()

    if db_host and db_user and db_name:
        params = ["charset=utf8mb4", "ssl_verify_cert=true", "ssl_verify_identity=true"]
        db_password_q = quote_plus(db_password)
        return (
            f"mysql+pymysql://{db_user}:{db_password_q}@{db_host}:{db_port}/{db_name}?"
            + "&".join(params)
        )

    return "sqlite:///icy_barber.db"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SERVER_NAME"] = os.getenv("SERVER_NAME", "127.0.0.1:8000")
_static_max_age_env = os.getenv("STATIC_MAX_AGE", "604800").strip()
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = int(_static_max_age_env) if _static_max_age_env.isdigit() else 604800
RESEND_API_KEY = (
    os.getenv("barberia_enviar", "").strip()
    or os.getenv("barberia_correos", "").strip()
    or os.getenv("RESEND_API_KEY", "").strip()
)
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "reservas@icybarber.me").strip() or "reservas@icybarber.me"
RESEND_REPLY_TO_EMAIL = os.getenv("RESEND_REPLY_TO_EMAIL", "").strip() or None
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_SMTP_HOST = os.getenv("RESEND_SMTP_HOST", "smtp.resend.com").strip() or "smtp.resend.com"
_resend_smtp_port_env = os.getenv("RESEND_SMTP_PORT", "587").strip()
RESEND_SMTP_PORT = int(_resend_smtp_port_env) if _resend_smtp_port_env.isdigit() else 587
RESEND_SMTP_USERNAME = os.getenv("RESEND_SMTP_USERNAME", "resend").strip() or "resend"
RESEND_SMTP_FALLBACK_ENABLED = os.getenv("RESEND_SMTP_FALLBACK", "true").strip().lower() not in {"0", "false", "no", "off"}

BASE_DIR = Path(__file__).resolve().parent
AVATAR_UPLOAD_DIR = BASE_DIR / "static" / "img" / "uploads"
PRODUCT_UPLOAD_DIR = BASE_DIR / "static" / "img" / "uploads"
PORTFOLIO_UPLOAD_DIR = BASE_DIR / "static" / "img" / "portfolio"
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_PRODUCT_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_PORTFOLIO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
DEFAULT_AVATAR = "camilo.jpg"
AVATAR_MAX_SIZE = int(os.getenv("AVATAR_MAX_SIZE", "320"))
AVATAR_WEBP_QUALITY = int(os.getenv("AVATAR_WEBP_QUALITY", "76"))
BARBERSHOP_INFO = {
    "name": "Icy Barber",
    "category": "Barberia",
    "address": "C. Barranca Seca 1, Barrio de Xochicalco, 90740 Zacatelco, Tlax, Mexico",
    "maps_url": "https://maps.google.com/?q=C.+Barranca+Seca+1,+Barrio+de+Xochicalco,+90740+Zacatelco,+Tlax.+Puebla+(Puebla),+Mexico",
    "phone": "222 506 0172",
    "whatsapp": "222 506 0172",
    "whatsapp_url": "https://wa.me/522225060172",
    "email": "contacto@icybarber.com",
    "instagram_url": "https://www.instagram.com/icy_barber?igsh=OHF5eDJxMmd2Ymhh",
    "instagram_label": "Instagram",
    "portfolio_image": "img/logo_icy.jpeg",
    "schedule": [
        {"iso_day": 1, "day": "Lunes", "open": "08:40", "close": "20:00"},
        {"iso_day": 2, "day": "Martes", "open": "09:00", "close": "20:00"},
        {"iso_day": 3, "day": "Miercoles", "open": "09:00", "close": "20:00"},
        {"iso_day": 4, "day": "Jueves", "open": "08:40", "close": "20:00"},
        {"iso_day": 5, "day": "Viernes", "open": "08:40", "close": "20:00"},
        {"iso_day": 6, "day": "Sabado", "open": "09:00", "close": "20:00"},
        {"iso_day": 7, "day": "Domingo", "open": "10:00", "close": "20:30"},
    ],
}
CANONICAL_SERVICES = [
    {
        "nombre": "Corte",
        "duracion_minutos": 40,
        "precio_efectivo": 100,
        "descripcion": "Corte de cabello con acabado limpio y estilo personalizado.",
    },
    {
        "nombre": "Corte y arreglo de barba",
        "duracion_minutos": 40,
        "precio_efectivo": 100,
        "descripcion": "Corte de cabello con perfilado y arreglo profesional de barba.",
    },
    {
        "nombre": "Corte y arreglo de ceja",
        "duracion_minutos": 40,
        "precio_efectivo": 100,
        "descripcion": "Corte de cabello con definición y arreglo estético de ceja.",
    },
]

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


DAY_NAMES = {1: "Lunes", 2: "Martes", 3: "Miercoles", 4: "Jueves", 5: "Viernes", 6: "Sabado", 7: "Domingo"}


def build_dynamic_schedule():
    """Build the weekly schedule from the earliest/latest barber hours per day."""
    today_iso = date.today().isoweekday()
    schedule = []
    today_hours = ""

    for day_num in range(1, 8):
        horarios = (
            HorarioBarbero.query
            .join(Barbero, HorarioBarbero.barbero_id == Barbero.id)
            .filter(HorarioBarbero.dia_semana == day_num, HorarioBarbero.activo == True, Barbero.activo == True)
            .all()
        )
        is_today = day_num == today_iso
        if horarios:
            open_time = min(h.hora_inicio for h in horarios)
            close_time = max(h.hora_fin for h in horarios)
            entry = {
                "iso_day": day_num,
                "day": DAY_NAMES[day_num],
                "open": open_time.strftime("%H:%M"),
                "close": close_time.strftime("%H:%M"),
                "is_today": is_today,
                "closed": False,
            }
            if is_today:
                today_hours = f"{entry['open']} - {entry['close']}"
        else:
            entry = {
                "iso_day": day_num,
                "day": DAY_NAMES[day_num],
                "open": "—",
                "close": "—",
                "is_today": is_today,
                "closed": True,
            }
            if is_today:
                today_hours = "Cerrado"
        schedule.append(entry)

    return schedule, today_hours


@app.context_processor
def inject_barbershop_info():
    info = dict(BARBERSHOP_INFO)
    try:
        schedule, today_hours = build_dynamic_schedule()
        info["schedule"] = schedule
        info["today_hours"] = today_hours
    except Exception:
        today_iso = date.today().isoweekday()
        schedule = []
        for row in BARBERSHOP_INFO["schedule"]:
            entry = dict(row)
            entry["is_today"] = entry.get("iso_day") == today_iso
            if entry["is_today"]:
                info["today_hours"] = f"{entry['open']} - {entry['close']}"
            schedule.append(entry)
        info["schedule"] = schedule
    return {"barbershop_info": info}


servicio_barberos = db.Table(
    "servicio_barberos",
    db.Column("servicio_id", db.Integer, db.ForeignKey("servicios.id"), primary_key=True),
    db.Column("barbero_id", db.Integer, db.ForeignKey("barberos.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Barbero(db.Model):
    __tablename__ = "barberos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=True)
    avatar = db.Column(db.String(255), nullable=False, default="camilo.jpg")
    telefono = db.Column(db.String(30), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)


class Servicio(db.Model):
    __tablename__ = "servicios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    duracion_minutos = db.Column(db.Integer, nullable=False)
    precio_efectivo = db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    barberos = db.relationship("Barbero", secondary=servicio_barberos, lazy="joined")


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(120), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(180), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)


class HorarioBarbero(db.Model):
    __tablename__ = "horarios_barbero"

    id = db.Column(db.Integer, primary_key=True)
    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)


class ExcepcionDisponibilidadBarbero(db.Model):
    __tablename__ = "excepciones_disponibilidad_barbero"

    id = db.Column(db.Integer, primary_key=True)
    # En algunos esquemas MySQL existentes, el tipo exacto de barberos.id no coincide
    # con INTEGER y provoca error 3780 al crear una FK nueva. Se mantiene integridad
    # a nivel aplicación y se indexa la columna para consultas eficientes.
    barbero_id = db.Column(db.Integer, nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # off | horario
    hora_inicio = db.Column(db.Time, nullable=True)
    hora_fin = db.Column(db.Time, nullable=True)
    motivo = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Cita(db.Model):
    __tablename__ = "citas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"), nullable=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="pendiente")
    origen = db.Column(db.String(50), nullable=False, default="Sitio web")
    pagado_efectivo = db.Column(db.Boolean, default=False, nullable=False)
    monto_efectivo = db.Column(db.Integer, nullable=True)
    cancel_token = db.Column(db.String(80), unique=True, index=True, nullable=True, default=lambda: uuid4().hex)
    canceled_at = db.Column(db.DateTime, nullable=True)

    cliente = db.relationship("Cliente")
    servicio = db.relationship("Servicio")
    barbero = db.relationship("Barbero")


class ProductoInventario(db.Model):
    __tablename__ = "productos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    id_item = db.Column(db.String(40), unique=True, nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    detalles = db.Column(db.Text, nullable=True)
    imagen = db.Column(db.String(255), nullable=True)
    precio = db.Column(db.Integer, nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, default=True, nullable=False)


class PortfolioImagen(db.Model):
    __tablename__ = "portfolio_imagenes"

    id = db.Column(db.Integer, primary_key=True)
    # Nullable para mantener compatibilidad: NULL = portafolio global de la barbería.
    barbero_id = db.Column(db.Integer, nullable=True, index=True)
    imagen = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*allowed_roles):
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in allowed_roles:
                flash("No tienes permisos para acceder a esta vista.", "error")
                return redirect(url_for("booking"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def allowed_avatar_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def optimize_and_save_avatar(file_storage, destination_path):
    resampling = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    with Image.open(file_storage.stream) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

        # Avatares se renderizan pequenos; limite cuadrado para reducir bytes y tiempo de descarga.
        img.thumbnail((AVATAR_MAX_SIZE, AVATAR_MAX_SIZE), resampling)
        img.save(
            destination_path,
            format="WEBP",
            quality=max(45, min(95, AVATAR_WEBP_QUALITY)),
            method=6,
        )


def allowed_product_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PRODUCT_EXTENSIONS


def allowed_portfolio_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PORTFOLIO_EXTENSIONS


def parse_days_input(raw_value):
    if raw_value is None:
        return []

    if isinstance(raw_value, list):
        values = raw_value
    else:
        values = [v.strip() for v in str(raw_value).split(",") if v.strip()]

    days = []
    for value in values:
        try:
            day = int(value)
            if 1 <= day <= 7:
                days.append(day)
        except (TypeError, ValueError):
            continue

    return sorted(set(days))


def normalize_avatar_name(value):
    avatar = str(value or "").strip()
    if not avatar or avatar.lower() in {"none", "null", "undefined"}:
        return DEFAULT_AVATAR
    return avatar


def resolve_avatar_filename(value):
    avatar = normalize_avatar_name(value)
    avatar_path = BASE_DIR / "static" / "img" / avatar
    if avatar_path.exists():
        return avatar
    return DEFAULT_AVATAR


def normalize_phone_10(raw_phone):
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) != 10:
        return None
    return digits


def send_resend_email_smtp(recipients, subject, html, text=None, reply_to=None):
    if not RESEND_API_KEY:
        return False

    message = EmailMessage()
    message["From"] = RESEND_FROM_EMAIL
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to

    plain_text = str(text or "").strip()
    if not plain_text:
        plain_text = re.sub(r"<[^>]+>", " ", str(html or ""))
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

    message.set_content(plain_text or "Confirmación de cita")
    if html:
        message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(RESEND_SMTP_HOST, RESEND_SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(RESEND_SMTP_USERNAME, RESEND_API_KEY)
            smtp.send_message(message)
        return True
    except Exception as exc:
        app.logger.warning("No se pudo enviar correo Resend vía SMTP: %s", exc)
        return False


def send_resend_email(to_email, subject, html, text=None, reply_to=None):
    if not RESEND_API_KEY:
        app.logger.warning("Resend no configurado: falta API key.")
        return False

    recipients = [to_email] if isinstance(to_email, str) else list(to_email or [])
    recipients = [str(email).strip().lower() for email in recipients if str(email).strip()]
    if not recipients:
        return False

    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to

    request = Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "IcyBarber/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response.read()
        return True
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            error_body = ""

        app.logger.warning(
            "No se pudo enviar correo Resend: HTTP %s %s | body=%s",
            getattr(exc, "code", "?"),
            getattr(exc, "reason", ""),
            error_body[:800],
        )

        if (
            RESEND_SMTP_FALLBACK_ENABLED
            and getattr(exc, "code", None) == 403
            and "error code: 1010" in error_body.lower()
        ):
            app.logger.warning("Resend API bloqueada por error 1010. Intentando fallback SMTP...")
            if send_resend_email_smtp(recipients, subject, html, text=text, reply_to=reply_to):
                app.logger.warning("Correo enviado por SMTP fallback tras bloqueo 1010 en API.")
                return True

        return False
    except (URLError, TimeoutError, ValueError) as exc:
        app.logger.warning("No se pudo enviar correo Resend: %s", exc)
        return False


def build_public_cancel_url(cancel_token):
        if not cancel_token:
                return None
        return url_for("public_cancel_cita", token=cancel_token, _external=True)


def build_booking_confirmation_email(customer_name, citas_rows):
        citas_rows = list(citas_rows or [])
        total = len(citas_rows)
        shop_name = html_escape(str(BARBERSHOP_INFO.get("name") or "Icy Barber"))
        shop_address = html_escape(str(BARBERSHOP_INFO.get("address") or ""))

        title = f"Reserva confirmada en {BARBERSHOP_INFO['name']}"
        intro = f"Hola {customer_name}, tu reservación quedó confirmada." if customer_name else "Tu reservación quedó confirmada."
        summary_label = "1 cita" if total == 1 else f"{total} citas"
        preheader = f"{summary_label} confirmada(s) en {BARBERSHOP_INFO['name']}."

        html_cards = []
        text_rows = []
        for row in citas_rows:
                service_name_raw = row.servicio.nombre if row.servicio else "Servicio"
                barber_name_raw = row.barbero.nombre if row.barbero else "Barbero"
                service_name = html_escape(str(service_name_raw))
                barber_name = html_escape(str(barber_name_raw))
                fecha_label = row.fecha.strftime("%d/%m/%Y")
                hora_inicio = row.hora_inicio.strftime("%H:%M")
                hora_fin = row.hora_fin.strftime("%H:%M")
                cancel_url = build_public_cancel_url(getattr(row, "cancel_token", None))

                action_html = ""
                action_text = ""
                if cancel_url:
                        cancel_url_safe = html_escape(cancel_url)
                        action_html = f"""
                        <tr>
                            <td style="padding:0 16px 16px 16px;">
                                <a href="{cancel_url_safe}" style="display:block;background:#9f1239;color:#ffffff;text-decoration:none;padding:11px 14px;border-radius:10px;font-weight:700;font-size:14px;text-align:center;">
                                    Cancelar cita
                                </a>
                            </td>
                        </tr>
                        """
                        action_text = f"Cancelación: {cancel_url}"

                html_cards.append(
                        f"""
                        <tr>
                            <td style="padding:0 0 12px 0;">
                                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #f2d6cf;background:#fff7f5;border-radius:14px;">
                                    <tr>
                                        <td style="padding:16px;">
                                            <p style="margin:0 0 8px 0;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#9f1239;font-weight:800;">{service_name}</p>
                                            <p style="margin:0 0 6px 0;font-size:24px;line-height:1.1;color:#111827;font-weight:800;">{fecha_label}</p>
                                            <p style="margin:0;font-size:14px;line-height:1.5;color:#374151;">{hora_inicio} - {hora_fin} · {barber_name}</p>
                                        </td>
                                    </tr>
                                    {action_html}
                                </table>
                            </td>
                        </tr>
                        """
                )
                text_rows.append(f"- {fecha_label} | {hora_inicio}-{hora_fin} | {service_name_raw} | {barber_name_raw}")
                if action_text:
                        text_rows.append(action_text)

        html = f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{html_escape(title)}</title>
        </head>
        <body style="margin:0;padding:0;background:#f3f4f6;">
            <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
                {html_escape(preheader)}
            </div>

            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;">
                <tr>
                    <td align="center" style="padding:18px 10px;">
                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:620px;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;">
                            <tr>
                                <td style="padding:24px 20px;background:#111827;">
                                    <p style="margin:0 0 10px 0;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:#d1d5db;font-weight:700;">{shop_name}</p>
                                    <h1 style="margin:0 0 10px 0;font-size:34px;line-height:1.12;color:#ffffff;font-weight:800;">{html_escape(title)}</h1>
                                    <p style="margin:0;font-size:16px;line-height:1.55;color:#e5e7eb;">{html_escape(intro)}</p>
                                </td>
                            </tr>

                            <tr>
                                <td style="padding:16px 20px 6px 20px;">
                                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="background:#111827;border-radius:999px;padding:7px 12px;color:#ffffff;font-size:12px;font-weight:700;">{html_escape(summary_label)}</td>
                                        </tr>
                                    </table>
                                    <p style="margin:10px 0 0 0;font-size:13px;line-height:1.5;color:#4b5563;">{shop_address}</p>
                                </td>
                            </tr>

                            <tr>
                                <td style="padding:12px 20px 6px 20px;">
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                        {''.join(html_cards)}
                                    </table>
                                </td>
                            </tr>

                            <tr>
                                <td style="padding:14px 20px 22px 20px;border-top:1px solid #e5e7eb;">
                                    <p style="margin:0;font-size:12px;line-height:1.65;color:#6b7280;">
                                        Si no solicitaste esta reserva, ignora este correo.<br>
                                        Si quieres reagendar o cancelar, usa el botón de cada cita antes de que la atiendan.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text = "\n".join([
                title,
                intro,
                f"Resumen: {summary_label}",
                f"Lugar: {BARBERSHOP_INFO['name']}",
                f"Dirección: {BARBERSHOP_INFO['address']}",
                f"Total de servicios: {total}",
                *text_rows,
                "Si no solicitaste esta reserva, ignora este correo.",
        ])
        return title, html, text


def notify_booking_confirmation(cliente, citas_rows):
    if not cliente or not cliente.email:
        return False

    customer_name = f"{cliente.nombres} {cliente.apellidos}".strip()
    subject, html, text = build_booking_confirmation_email(customer_name, citas_rows)
    return send_resend_email(
        cliente.email,
        subject,
        html,
        text=text,
        reply_to=RESEND_REPLY_TO_EMAIL,
    )


def normalize_product_image_name(value):
    image_name = str(value or "").strip()
    if not image_name or image_name.lower() in {"none", "null", "undefined"}:
        return None
    return image_name


def ensure_product_image_column():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "productos_inventario" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("productos_inventario")}
    if "imagen" in columns:
        return

    db.session.execute(text("ALTER TABLE productos_inventario ADD COLUMN imagen VARCHAR(255) NULL"))
    db.session.commit()


def ensure_portfolio_table():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "portfolio_imagenes" not in table_names:
        PortfolioImagen.__table__.create(bind=db.engine)
        return

    columns = {col["name"] for col in inspector.get_columns("portfolio_imagenes")}
    if "barbero_id" not in columns:
        db.session.execute(text("ALTER TABLE portfolio_imagenes ADD COLUMN barbero_id INTEGER NULL"))
        db.session.commit()

    if "sort_order" not in columns:
        db.session.execute(text("ALTER TABLE portfolio_imagenes ADD COLUMN sort_order INTEGER NULL"))
        db.session.commit()

    normalize_all_portfolio_orders()


def ensure_barbero_service_tables():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "excepciones_disponibilidad_barbero" not in table_names:
        ExcepcionDisponibilidadBarbero.__table__.create(bind=db.engine)


def ensure_cita_public_columns():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "citas" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("citas")}
    if "cancel_token" not in columns:
        db.session.execute(text("ALTER TABLE citas ADD COLUMN cancel_token VARCHAR(80) NULL"))
        db.session.commit()

    if "canceled_at" not in columns:
        db.session.execute(text("ALTER TABLE citas ADD COLUMN canceled_at TIMESTAMP NULL"))
        db.session.commit()

    pending_tokens = Cita.query.filter(Cita.cancel_token.is_(None)).all()
    if pending_tokens:
        for cita in pending_tokens:
            cita.cancel_token = uuid4().hex
        db.session.commit()

    indexes = {index["name"] for index in inspector.get_indexes("citas")}
    if "uq_citas_cancel_token" not in indexes:
        try:
            db.session.execute(text("CREATE UNIQUE INDEX uq_citas_cancel_token ON citas (cancel_token)"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def ensure_sample_products():
    samples = [
        {
            "id_item": "PROD-001",
            "nombre": "Pomada mate clásica",
            "detalles": "Fijación media con acabado natural para peinados diarios.",
            "precio": 28000,
            "stock": 12,
        },
        {
            "id_item": "PROD-002",
            "nombre": "Aceite para barba premium",
            "detalles": "Hidratación profunda con aroma suave y textura ligera.",
            "precio": 32000,
            "stock": 8,
        },
        {
            "id_item": "PROD-003",
            "nombre": "Shampoo anticaída",
            "detalles": "Limpieza diaria para fortalecer cabello y cuero cabelludo.",
            "precio": 35000,
            "stock": 10,
        },
    ]

    for sample in samples:
        exists = ProductoInventario.query.filter_by(id_item=sample["id_item"]).first()
        if exists:
            continue
        db.session.add(
            ProductoInventario(
                id_item=sample["id_item"],
                nombre=sample["nombre"],
                detalles=sample["detalles"],
                precio=sample["precio"],
                stock=sample["stock"],
                activo=True,
            )
        )

    db.session.commit()


def sync_service_catalog(reset_citas_on_change=True):
    canonical_names = {item["nombre"] for item in CANONICAL_SERVICES}
    active_barberos = Barbero.query.filter_by(activo=True).all()
    changed = False

    for item in CANONICAL_SERVICES:
        servicio = Servicio.query.filter_by(nombre=item["nombre"]).first()
        if not servicio:
            servicio = Servicio(
                nombre=item["nombre"],
                duracion_minutos=item["duracion_minutos"],
                precio_efectivo=item["precio_efectivo"],
                descripcion=item["descripcion"],
                activo=True,
            )
            db.session.add(servicio)
            db.session.flush()
            changed = True

        if servicio.duracion_minutos != item["duracion_minutos"]:
            servicio.duracion_minutos = item["duracion_minutos"]
            changed = True
        if servicio.precio_efectivo != item["precio_efectivo"]:
            servicio.precio_efectivo = item["precio_efectivo"]
            changed = True
        if servicio.descripcion != item["descripcion"]:
            servicio.descripcion = item["descripcion"]
            changed = True
        if not servicio.activo:
            servicio.activo = True
            changed = True

        current_ids = {b.id for b in servicio.barberos}
        target_ids = {b.id for b in active_barberos}
        if current_ids != target_ids:
            servicio.barberos = list(active_barberos)
            changed = True

    for servicio in Servicio.query.all():
        if servicio.nombre in canonical_names:
            continue
        if servicio.activo or servicio.barberos:
            servicio.activo = False
            servicio.barberos = []
            changed = True

    if changed and reset_citas_on_change:
        Cita.query.delete()

    db.session.commit()


def assign_barbero_to_active_servicios(barbero):
    servicios = Servicio.query.filter_by(activo=True).all()
    for servicio in servicios:
        if not any(existing.id == barbero.id for existing in servicio.barberos):
            servicio.barberos.append(barbero)


def set_barbero_horarios(barbero_id, dias_semana, hora_inicio, hora_fin):
    HorarioBarbero.query.filter_by(barbero_id=barbero_id).delete()
    for dia in dias_semana:
        db.session.add(
            HorarioBarbero(
                barbero_id=barbero_id,
                dia_semana=dia,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                activo=True,
            )
        )


def get_barbero_override_for_date(barbero_id, fecha_cita):
    return (
        ExcepcionDisponibilidadBarbero.query
        .filter_by(barbero_id=barbero_id, fecha=fecha_cita, activo=True)
        .order_by(ExcepcionDisponibilidadBarbero.id.desc())
        .first()
    )


def get_effective_work_ranges(barbero_id, fecha_cita):
    barbero = db.session.get(Barbero, barbero_id)
    if not barbero or not barbero.activo:
        return []

    override = get_barbero_override_for_date(barbero_id, fecha_cita)
    if override:
        if override.tipo == "off":
            return []
        if override.tipo == "horario" and override.hora_inicio and override.hora_fin and override.hora_fin > override.hora_inicio:
            return [(override.hora_inicio, override.hora_fin)]
        return []

    dia_semana = fecha_cita.isoweekday()
    horarios = HorarioBarbero.query.filter_by(barbero_id=barbero_id, dia_semana=dia_semana, activo=True).all()
    return [(h.hora_inicio, h.hora_fin) for h in horarios if h.hora_fin > h.hora_inicio]


def barbero_en_servicio(servicio, barbero_id):
    return any(b.id == barbero_id for b in servicio.barberos)


def has_schedule_coverage(barbero_id, fecha_cita, hora_inicio, hora_fin):
    ranges = get_effective_work_ranges(barbero_id, fecha_cita)
    return any(start <= hora_inicio and end >= hora_fin for start, end in ranges)


def has_overlap(barbero_id, fecha_cita, hora_inicio, hora_fin, exclude_cita_id=None):
    query = Cita.query.filter_by(barbero_id=barbero_id, fecha=fecha_cita).filter(Cita.estado != "cancelada")
    if exclude_cita_id:
        query = query.filter(Cita.id != exclude_cita_id)

    conflict = (
        query.filter(Cita.hora_inicio < hora_fin)
        .filter(Cita.hora_fin > hora_inicio)
        .first()
    )
    return conflict is not None


def time_to_minutes(value):
    return value.hour * 60 + value.minute


def minutes_to_time(value):
    return datetime.strptime(f"{value // 60:02d}:{value % 60:02d}", "%H:%M").time()


def generate_available_slots(barbero_id, fecha_cita, duracion_minutos, step_minutes=40):
    ranges = get_effective_work_ranges(barbero_id, fecha_cita)
    if not ranges:
        return []

    is_today = fecha_cita == date.today()
    now_minutes = None
    if is_today:
        now_dt = datetime.now()
        now_minutes = (now_dt.hour * 60) + now_dt.minute

    existing = (
        Cita.query.filter_by(barbero_id=barbero_id, fecha=fecha_cita)
        .filter(Cita.estado != "cancelada")
        .all()
    )

    slots = []
    for start_time_range, end_time_range in ranges:
        start = time_to_minutes(start_time_range)
        end = time_to_minutes(end_time_range)
        cursor = start

        while cursor + duracion_minutos <= end:
            if is_today and now_minutes is not None and cursor <= now_minutes:
                cursor += step_minutes
                continue

            start_time = minutes_to_time(cursor)
            end_time = minutes_to_time(cursor + duracion_minutos)

            overlapped = any(
                c.hora_inicio < end_time and c.hora_fin > start_time
                for c in existing
            )
            if not overlapped:
                slots.append(start_time.strftime("%H:%M"))

            cursor += step_minutes

    return slots


def get_effective_work_ranges_bulk(barbero_ids, fecha_cita):
    if not barbero_ids:
        return {}

    dia_semana = fecha_cita.isoweekday()
    horarios = (
        HorarioBarbero.query
        .filter(HorarioBarbero.barbero_id.in_(barbero_ids))
        .filter(HorarioBarbero.dia_semana == dia_semana)
        .filter(HorarioBarbero.activo == True)
        .all()
    )

    schedule_ranges = {barbero_id: [] for barbero_id in barbero_ids}
    for horario in horarios:
        if horario.hora_fin > horario.hora_inicio:
            schedule_ranges.setdefault(horario.barbero_id, []).append((horario.hora_inicio, horario.hora_fin))

    overrides = (
        ExcepcionDisponibilidadBarbero.query
        .filter(ExcepcionDisponibilidadBarbero.barbero_id.in_(barbero_ids))
        .filter(ExcepcionDisponibilidadBarbero.fecha == fecha_cita)
        .filter(ExcepcionDisponibilidadBarbero.activo == True)
        .order_by(ExcepcionDisponibilidadBarbero.id.desc())
        .all()
    )

    latest_override_by_barbero = {}
    for override in overrides:
        if override.barbero_id not in latest_override_by_barbero:
            latest_override_by_barbero[override.barbero_id] = override

    effective_ranges = {}
    for barbero_id in barbero_ids:
        override = latest_override_by_barbero.get(barbero_id)
        if not override:
            effective_ranges[barbero_id] = schedule_ranges.get(barbero_id, [])
            continue

        if override.tipo == "off":
            effective_ranges[barbero_id] = []
        elif override.tipo == "horario" and override.hora_inicio and override.hora_fin and override.hora_fin > override.hora_inicio:
            effective_ranges[barbero_id] = [(override.hora_inicio, override.hora_fin)]
        else:
            effective_ranges[barbero_id] = []

    return effective_ranges


def generate_available_slots_bulk(barbero_ids, fecha_cita, duracion_minutos, step_minutes=40):
    if not barbero_ids:
        return {}

    ranges_by_barbero = get_effective_work_ranges_bulk(barbero_ids, fecha_cita)
    existing_citas = (
        Cita.query
        .filter(Cita.barbero_id.in_(barbero_ids))
        .filter(Cita.fecha == fecha_cita)
        .filter(Cita.estado != "cancelada")
        .all()
    )

    existing_by_barbero = {barbero_id: [] for barbero_id in barbero_ids}
    for cita in existing_citas:
        existing_by_barbero.setdefault(cita.barbero_id, []).append(cita)

    is_today = fecha_cita == date.today()
    now_minutes = None
    if is_today:
        now_dt = datetime.now()
        now_minutes = (now_dt.hour * 60) + now_dt.minute

    slots_by_barbero = {}
    for barbero_id in barbero_ids:
        ranges = ranges_by_barbero.get(barbero_id, [])
        if not ranges:
            slots_by_barbero[str(barbero_id)] = []
            continue

        existing = existing_by_barbero.get(barbero_id, [])
        slots = []
        for start_time_range, end_time_range in ranges:
            start = time_to_minutes(start_time_range)
            end = time_to_minutes(end_time_range)
            cursor = start

            while cursor + duracion_minutos <= end:
                if is_today and now_minutes is not None and cursor <= now_minutes:
                    cursor += step_minutes
                    continue

                start_time = minutes_to_time(cursor)
                end_time = minutes_to_time(cursor + duracion_minutos)

                overlapped = any(
                    c.hora_inicio < end_time and c.hora_fin > start_time
                    for c in existing
                )
                if not overlapped:
                    slots.append(start_time.strftime("%H:%M"))

                cursor += step_minutes

        slots_by_barbero[str(barbero_id)] = slots

    return slots_by_barbero


def serialize_barbero_excepcion(excepcion):
    return {
        "id": excepcion.id,
        "fecha": excepcion.fecha.isoformat(),
        "tipo": excepcion.tipo,
        "hora_inicio": excepcion.hora_inicio.strftime("%H:%M") if excepcion.hora_inicio else None,
        "hora_fin": excepcion.hora_fin.strftime("%H:%M") if excepcion.hora_fin else None,
        "motivo": excepcion.motivo or "",
        "activo": bool(excepcion.activo),
    }


def build_username_from_nombre(nombre, fallback):
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", nombre.lower())
    cleaned = cleaned or fallback
    return cleaned[:30]


def validate_password_strength(password):
    pwd = str(password or "")
    if len(pwd) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Z]", pwd):
        return "La contraseña debe incluir al menos una mayúscula."
    if not re.search(r"[a-z]", pwd):
        return "La contraseña debe incluir al menos una minúscula."
    if not re.search(r"\d", pwd):
        return "La contraseña debe incluir al menos un número."
    if not re.search(r"[!@#$%^&*.]", pwd):
        return "La contraseña debe incluir al menos un carácter especial (incluye ., !, @, #, $, %, ^, &, *)."
    return None


def should_bootstrap():
    configured = os.getenv("AUTO_BOOTSTRAP_DB")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes", "on"}
    return app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")


def ensure_admin_from_env():
    admin_username = os.getenv("ADMIN_USERNAME", "icy_barber").strip() or "icy_barber"
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        return

    if admin_username != "admin":
        legacy_admin = User.query.filter_by(username="admin").first()
        if legacy_admin:
            db.session.delete(legacy_admin)

    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        admin = User(username=admin_username, role="admin", activo=True)
        db.session.add(admin)

    admin.role = "admin"
    admin.activo = True
    admin.barbero_id = None
    admin.set_password(admin_password)
    db.session.commit()


def seed_data():
    if Barbero.query.count() > 0:
        return

    # Limpia asociaciones residuales si hubo una migración de esquema local.
    db.session.execute(servicio_barberos.delete())

    barberos = [
        Barbero(nombre="Camilo", avatar="camilo.jpg", telefono="3001112233", email="camilo@icybarber.local"),
        Barbero(nombre="Diego", avatar="diego.jpg", telefono="3001112244", email="diego@icybarber.local"),
        Barbero(nombre="Jaime", avatar="jaime.jpg", telefono="3001112255", email="jaime@icybarber.local"),
        Barbero(nombre="Angel", avatar="angel.jpg", telefono="3001112266", email="angel@icybarber.local"),
    ]
    db.session.add_all(barberos)
    db.session.flush()

    servicios = [
        Servicio(
            nombre=item["nombre"],
            duracion_minutos=item["duracion_minutos"],
            precio_efectivo=item["precio_efectivo"],
            descripcion=item["descripcion"],
            barberos=barberos,
        )
        for item in CANONICAL_SERVICES
    ]
    db.session.add_all(servicios)
    db.session.flush()

    for barbero in barberos:
        for dia_semana in [1, 2, 3, 4, 5]:
            db.session.add(
                HorarioBarbero(
                    barbero_id=barbero.id,
                    dia_semana=dia_semana,
                    hora_inicio=parse_time("09:00"),
                    hora_fin=parse_time("18:00"),
                    activo=True,
                )
            )

    clientes = [
        Cliente(nombres="Cristian", apellidos="Rodriguez", telefono="3001000001", email="cristian@example.com"),
        Cliente(nombres="Rodrigo", apellidos="Torres", telefono="3001000002", email="rodrigo@example.com"),
        Cliente(nombres="Camilo", apellidos="Castillo", telefono="3001000003", email="camilo@example.com"),
        Cliente(nombres="Jose", apellidos="Molero", telefono="3001000004", email="jose@example.com"),
    ]
    db.session.add_all(clientes)
    db.session.flush()

    admin = User(username="admin", role="admin", activo=True)
    admin.set_password("admin123")
    db.session.add(admin)

    for i, b in enumerate(barberos, start=1):
        user = User(username=f"barbero{i}", role="barbero", barbero_id=b.id, activo=True)
        user.set_password("temp123")
        db.session.add(user)

    db.session.commit()


def serialize_barbero(barbero):
    horarios = HorarioBarbero.query.filter_by(barbero_id=barbero.id, activo=True).all()
    dias_map = {1: "Lun", 2: "Mar", 3: "Mie", 4: "Jue", 5: "Vie", 6: "Sab", 7: "Dom"}
    dias_semana = sorted([h.dia_semana for h in horarios])
    dias_trabajo = ", ".join(dias_map.get(h.dia_semana, str(h.dia_semana)) for h in horarios)
    hora_inicio = min((h.hora_inicio for h in horarios), default=None)
    hora_fin = max((h.hora_fin for h in horarios), default=None)
    
    user = User.query.filter_by(barbero_id=barbero.id).first()
    username = user.username if user else None

    avatar_filename = resolve_avatar_filename(barbero.avatar)

    return {
        "id": barbero.id,
        "nombre": barbero.nombre,
        "email": barbero.email,
        "avatar": avatar_filename,
        "telefono": barbero.telefono,
        "username": username,
        "dias_semana": dias_semana,
        "dias_trabajo": dias_trabajo,
        "hora_inicio": hora_inicio.strftime("%H:%M") if hora_inicio else None,
        "hora_fin": hora_fin.strftime("%H:%M") if hora_fin else None,
        "avatar_url": url_for("static", filename="img/" + avatar_filename),
        "activo": barbero.activo,
    }


SERVICE_ICONS = {
    "corte": '<svg class="service-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>',
    "barba": '<svg class="service-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c-4 0-8-2.5-8-8V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8c0 5.5-4 8-8 8Z"/><path d="M8 10v2c0 2.2 1.8 4 4 4s4-1.8 4-4v-2"/><line x1="8" y1="6" x2="8" y2="8"/><line x1="16" y1="6" x2="16" y2="8"/></svg>',
    "ceja": '<svg class="service-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10c3-4 7-5 10-3"/><path d="M21 10c-3-4-7-5-10-3"/><circle cx="8" cy="14" r="2"/><circle cx="16" cy="14" r="2"/></svg>',
    "default": '<svg class="service-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>',
}


def _get_service_icon(nombre):
    return SERVICE_ICONS["corte"]


def serialize_servicio(servicio):
    return {
        "id": servicio.id,
        "nombre": servicio.nombre,
        "duracion": f"{servicio.duracion_minutos} min",
        "precio": servicio.precio_efectivo,
        "descripcion": servicio.descripcion,
        "descuento": False,
        "barberos": [b.id for b in servicio.barberos],
        "icon_svg": _get_service_icon(servicio.nombre),
    }


def serialize_producto(producto):
    image_name = normalize_product_image_name(producto.imagen)
    return {
        "id": producto.id,
        "id_item": producto.id_item,
        "nombre": producto.nombre,
        "detalles": producto.detalles or "",
        "imagen": image_name,
        "imagen_url": url_for("static", filename=f"img/{image_name}") if image_name else None,
        "precio": int(producto.precio or 0),
        "stock": int(producto.stock or 0),
        "activo": bool(producto.activo),
    }


def serialize_cita(cita):
    cliente_nombre = f"{cita.cliente.nombres} {cita.cliente.apellidos}".strip() if cita.cliente else "Cliente"
    servicio_nombre = cita.servicio.nombre if cita.servicio else "Servicio"
    return {
        "id": cita.id,
        "fecha": cita.fecha.isoformat(),
        "hora_inicio": cita.hora_inicio.strftime("%H:%M"),
        "hora_fin": cita.hora_fin.strftime("%H:%M"),
        "cliente": cliente_nombre,
        "servicio": servicio_nombre,
        "barbero_id": cita.barbero_id,
        "estado": cita.estado,
        "origen": cita.origen,
        "pagado": bool(cita.pagado_efectivo),
        "cliente_id": cita.cliente_id,
        "servicio_id": cita.servicio_id,
    }


def serialize_portfolio_image(item):
    return {
        "id": item.id,
        "barbero_id": item.barbero_id,
        "imagen": item.imagen,
        "imagen_url": url_for("static", filename=f"img/portfolio/{item.imagen}"),
        "sort_order": item.sort_order,
        "activo": bool(item.activo),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def get_portfolio_items_ordered(only_active=True, barbero_scope="all", barbero_id=None):
    query = PortfolioImagen.query
    if only_active:
        query = query.filter_by(activo=True)

    if barbero_scope == "global":
        query = query.filter(PortfolioImagen.barbero_id.is_(None))
    elif barbero_scope == "barber":
        if barbero_id is None:
            return []
        query = query.filter(PortfolioImagen.barbero_id == barbero_id)

    items = query.all()
    return sorted(
        items,
        key=lambda x: (
            x.sort_order is None,
            x.sort_order if x.sort_order is not None else 10**9,
            x.id,
        ),
    )


def normalize_portfolio_order(barbero_scope="global", barbero_id=None):
    items = get_portfolio_items_ordered(
        only_active=False,
        barbero_scope=barbero_scope,
        barbero_id=barbero_id,
    )
    changed = False
    for idx, item in enumerate(items, start=1):
        if item.sort_order != idx:
            item.sort_order = idx
            changed = True
    if changed:
        db.session.commit()


def normalize_all_portfolio_orders():
    normalize_portfolio_order(barbero_scope="global")
    barber_ids = [
        row[0]
        for row in db.session.query(PortfolioImagen.barbero_id)
        .filter(PortfolioImagen.barbero_id.isnot(None))
        .distinct()
        .all()
    ]
    for barber_id in barber_ids:
        normalize_portfolio_order(barbero_scope="barber", barbero_id=barber_id)


def get_next_portfolio_order(barbero_scope="global", barbero_id=None):
    items = get_portfolio_items_ordered(
        only_active=False,
        barbero_scope=barbero_scope,
        barbero_id=barbero_id,
    )
    if not items:
        return 1
    return max(int(item.sort_order or 0) for item in items) + 1


def get_payload():
    return request.get_json(silent=True) or request.form


def auto_complete_overdue_citas():
    """Marca como completadas las citas ya vencidas que siguen activas."""
    now_dt = datetime.now()
    pending_states = ["pendiente", "confirmada", "reagendada"]
    citas = Cita.query.filter(Cita.estado.in_(pending_states)).all()

    changed = False
    for cita in citas:
        cita_end_dt = datetime.combine(cita.fecha, cita.hora_fin)
        if cita_end_dt <= now_dt:
            cita.estado = "completada"
            changed = True

    if changed:
        db.session.commit()


@app.route("/")
def booking():
    barberos = [serialize_barbero(b) for b in Barbero.query.filter_by(activo=True).order_by(Barbero.id.asc()).all()]
    servicios = [serialize_servicio(s) for s in Servicio.query.filter_by(activo=True).all()]
    productos = [
        serialize_producto(p)
        for p in ProductoInventario.query.filter_by(activo=True).order_by(ProductoInventario.id.asc()).all()
    ]
    portfolio_images = [
        serialize_portfolio_image(p)
        for p in get_portfolio_items_ordered(only_active=True, barbero_scope="global")
    ]
    team_portfolios = {
        str(barbero["id"]): [
            serialize_portfolio_image(item)
            for item in get_portfolio_items_ordered(
                only_active=True,
                barbero_scope="barber",
                barbero_id=barbero["id"],
            )
        ]
        for barbero in barberos
    }
    return render_template(
        "booking.html",
        barberos=barberos,
        servicios=servicios,
        productos=productos,
        portfolio_images=portfolio_images,
        team_portfolios=team_portfolios,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("dashboard_admin"))
        return redirect(url_for("dashboard_barbero"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        keep_session_active = request.form.get("keep_session") == "on"
        user = User.query.filter_by(username=username, activo=True).first()

        if not user or not user.check_password(password):
            flash("Credenciales inválidas", "error")
            return render_template("login.html"), 401

        login_user(user, remember=keep_session_active)
        session["keep_session_active"] = keep_session_active
        flash("Inicio de sesión exitoso", "success")
        if user.role == "admin":
            return redirect(url_for("dashboard_admin"))
        return redirect(url_for("dashboard_barbero"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("keep_session_active", None)
    return redirect(url_for("booking"))


@app.route("/admin")
@role_required("admin")
def dashboard_admin():
    auto_complete_overdue_citas()
    barberos = [serialize_barbero(b) for b in Barbero.query.filter_by(activo=True).all()]
    citas = [serialize_cita(c) for c in Cita.query.order_by(Cita.id.asc()).all()]
    return render_template(
        "dashboard.html",
        barberos=barberos,
        citas=citas,
        keep_session_active=bool(session.get("keep_session_active", False)),
    )


@app.route("/barbero")
@role_required("barbero")
def dashboard_barbero():
    auto_complete_overdue_citas()
    barbero = db.session.get(Barbero, current_user.barbero_id)
    if not barbero:
        flash("No se encontró el perfil del barbero", "error")
        return redirect(url_for("booking"))

    barberos = [serialize_barbero(barbero)]
    citas = [
        serialize_cita(c)
        for c in Cita.query.filter_by(barbero_id=barbero.id).order_by(Cita.id.asc()).all()
    ]
    return render_template(
        "dashboard.html",
        barberos=barberos,
        citas=citas,
        keep_session_active=bool(session.get("keep_session_active", False)),
    )


@app.route("/api/barberos")
def api_barberos():
    return jsonify([serialize_barbero(b) for b in Barbero.query.filter_by(activo=True).order_by(Barbero.id.asc()).all()])


@app.route("/api/servicios")
def api_servicios():
    return jsonify([serialize_servicio(s) for s in Servicio.query.filter_by(activo=True).all()])


@app.route("/api/productos")
def api_productos_public():
    productos = [
        serialize_producto(p)
        for p in ProductoInventario.query.filter_by(activo=True).order_by(ProductoInventario.id.asc()).all()
    ]
    return jsonify(productos)


@app.route("/api/disponibilidad")
def api_disponibilidad():
    servicio_id = request.args.get("servicio_id", type=int)
    fecha_str = request.args.get("fecha", "").strip()

    if not servicio_id or not fecha_str:
        return jsonify({"error": "Debes enviar servicio_id y fecha (YYYY-MM-DD)."}), 400

    try:
        fecha_cita = parse_date(fecha_str)
    except ValueError:
        return jsonify({"error": "Fecha inválida."}), 400

    servicio = Servicio.query.filter_by(id=servicio_id, activo=True).first()
    if not servicio:
        return jsonify({"error": "Servicio no disponible."}), 404

    barberos = [b for b in servicio.barberos if b.activo]
    barbero_ids = [b.id for b in barberos]
    slots = generate_available_slots_bulk(
        barbero_ids,
        fecha_cita,
        servicio.duracion_minutos,
        step_minutes=40,
    )

    return jsonify(
        {
            "servicio_id": servicio_id,
            "fecha": fecha_cita.isoformat(),
            "barberos": [serialize_barbero(b) for b in barberos],
            "slots": slots,
        }
    )


@app.route("/api/citas")
@login_required
def api_citas():
    auto_complete_overdue_citas()
    if current_user.role == "admin":
        citas = Cita.query.order_by(Cita.id.asc()).all()
    elif current_user.role == "barbero":
        citas = Cita.query.filter_by(barbero_id=current_user.barbero_id).order_by(Cita.id.asc()).all()
    else:
        citas = []
    return jsonify([serialize_cita(c) for c in citas])


@app.route("/api/citas/public", methods=["POST"])
def api_create_cita_public():
    data = get_payload()

    required_fields = [
        "nombres",
        "apellidos",
        "telefono",
        "email",
        "servicio_id",
        "barbero_id",
        "fecha",
        "hora_inicio",
    ]
    missing = [f for f in required_fields if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Campos obligatorios faltantes: {', '.join(missing)}"}), 400

    try:
        servicio_id = int(data.get("servicio_id"))
        barbero_id = int(data.get("barbero_id"))
        fecha_cita = parse_date(data.get("fecha"))
        hora_inicio = parse_time(data.get("hora_inicio"))
    except (TypeError, ValueError):
        return jsonify({"error": "Formato inválido en servicio, barbero, fecha u hora."}), 400

    servicio = Servicio.query.filter_by(id=servicio_id, activo=True).first()
    barbero = Barbero.query.filter_by(id=barbero_id, activo=True).first()

    if not servicio or not barbero:
        return jsonify({"error": "Servicio o barbero no disponible."}), 404

    if not barbero_en_servicio(servicio, barbero_id):
        return jsonify({"error": "El barbero seleccionado no presta ese servicio."}), 400

    hora_fin_dt = datetime.combine(fecha_cita, hora_inicio) + timedelta(minutes=servicio.duracion_minutos)
    hora_fin = hora_fin_dt.time()

    available_slots = generate_available_slots(
        barbero_id,
        fecha_cita,
        servicio.duracion_minutos,
        step_minutes=40,
    )
    if hora_inicio.strftime("%H:%M") not in available_slots:
        return jsonify({"error": "La hora seleccionada no está disponible en lapsos de 40 minutos."}), 400

    if not has_schedule_coverage(barbero_id, fecha_cita, hora_inicio, hora_fin):
        return jsonify({"error": "La hora seleccionada está fuera del horario laboral del barbero."}), 400

    if has_overlap(barbero_id, fecha_cita, hora_inicio, hora_fin):
        return jsonify({"error": "Ya existe una cita en ese rango horario. Elige otra hora."}), 409

    email = data.get("email", "").strip().lower()
    telefono = normalize_phone_10(data.get("telefono", ""))
    if not telefono:
        return jsonify({"error": "El teléfono debe contener exactamente 10 dígitos."}), 400

    cliente = Cliente.query.filter_by(email=email, telefono=telefono).first()
    if not cliente:
        cliente = Cliente(
            nombres=data.get("nombres", "").strip(),
            apellidos=data.get("apellidos", "").strip(),
            telefono=telefono,
            email=email,
            activo=True,
        )
        db.session.add(cliente)
        db.session.flush()

    cita = Cita(
        cliente_id=cliente.id,
        barbero_id=barbero_id,
        servicio_id=servicio_id,
        fecha=fecha_cita,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        estado="pendiente",
        origen="Sitio web",
        pagado_efectivo=False,
    )
    db.session.add(cita)
    db.session.commit()
    notify_booking_confirmation(cliente, [cita])

    return jsonify({"message": "Cita creada correctamente.", "cita": serialize_cita(cita)}), 201


@app.route("/api/citas/public/lote", methods=["POST"])
def api_create_citas_public_batch():
    data = request.get_json(silent=True) or {}
    required_fields = ["nombres", "apellidos", "telefono", "email", "items"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Campos obligatorios faltantes: {', '.join(missing)}"}), 400

    items = data.get("items") or []
    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "Debes enviar al menos un servicio en items."}), 400

    email = str(data.get("email", "")).strip().lower()
    telefono = normalize_phone_10(data.get("telefono", ""))
    if not telefono:
        return jsonify({"error": "El teléfono debe contener exactamente 10 dígitos."}), 400

    cliente = Cliente.query.filter_by(email=email, telefono=telefono).first()
    if not cliente:
        cliente = Cliente(
            nombres=str(data.get("nombres", "")).strip(),
            apellidos=str(data.get("apellidos", "")).strip(),
            telefono=telefono,
            email=email,
            activo=True,
        )
        db.session.add(cliente)
        db.session.flush()

    prepared = []
    local_ranges = []
    for idx, item in enumerate(items):
        try:
            servicio_id = int(item.get("servicio_id"))
            barbero_id = int(item.get("barbero_id"))
            fecha_cita = parse_date(item.get("fecha"))
            hora_inicio = parse_time(item.get("hora_inicio"))
        except (TypeError, ValueError):
            return jsonify({"error": f"Item {idx + 1}: formato inválido."}), 400

        servicio = Servicio.query.filter_by(id=servicio_id, activo=True).first()
        barbero = Barbero.query.filter_by(id=barbero_id, activo=True).first()
        if not servicio or not barbero:
            return jsonify({"error": f"Item {idx + 1}: servicio o barbero no disponible."}), 404

        if not barbero_en_servicio(servicio, barbero_id):
            return jsonify({"error": f"Item {idx + 1}: barbero no presta ese servicio."}), 400

        hora_fin_dt = datetime.combine(fecha_cita, hora_inicio) + timedelta(minutes=servicio.duracion_minutos)
        hora_fin = hora_fin_dt.time()

        available_slots = generate_available_slots(
            barbero_id,
            fecha_cita,
            servicio.duracion_minutos,
            step_minutes=40,
        )
        if hora_inicio.strftime("%H:%M") not in available_slots:
            return jsonify({"error": f"Item {idx + 1}: hora inválida para lapsos de 40 minutos."}), 400

        if not has_schedule_coverage(barbero_id, fecha_cita, hora_inicio, hora_fin):
            return jsonify({"error": f"Item {idx + 1}: fuera del horario laboral."}), 400

        if has_overlap(barbero_id, fecha_cita, hora_inicio, hora_fin):
            return jsonify({"error": f"Item {idx + 1}: ya existe una cita en ese rango."}), 409

        for rng in local_ranges:
            if rng["barbero_id"] == barbero_id and rng["fecha"] == fecha_cita:
                if rng["inicio"] < hora_fin and rng["fin"] > hora_inicio:
                    return jsonify({"error": f"Item {idx + 1}: conflicto con otro servicio seleccionado."}), 409

        prepared.append(
            Cita(
                cliente_id=cliente.id,
                barbero_id=barbero_id,
                servicio_id=servicio_id,
                fecha=fecha_cita,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                estado="pendiente",
                origen="Sitio web",
                pagado_efectivo=False,
            )
        )
        local_ranges.append({"barbero_id": barbero_id, "fecha": fecha_cita, "inicio": hora_inicio, "fin": hora_fin})

    db.session.add_all(prepared)
    db.session.commit()
    notify_booking_confirmation(cliente, prepared)

    return jsonify({"message": "Reservación creada correctamente.", "citas": [serialize_cita(c) for c in prepared]}), 201


@app.route("/api/admin/barberos", methods=["GET"])
@role_required("admin")
def api_admin_barberos_list():
    barberos = [serialize_barbero(b) for b in Barbero.query.order_by(Barbero.id.asc()).all()]
    return jsonify(barberos)


@app.route("/api/admin/barberos/avatar", methods=["POST"])
@role_required("admin")
def api_admin_barberos_avatar_upload():
    file = request.files.get("avatar")
    if not file or not file.filename:
        return jsonify({"error": "Debes seleccionar una imagen."}), 400

    if not allowed_avatar_file(file.filename):
        return jsonify({"error": "Formato inválido. Usa PNG, JPG, JPEG o WEBP."}), 400

    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    if "." not in safe_name:
        return jsonify({"error": "Nombre de archivo inválido."}), 400

    final_name = f"barbero_{uuid4().hex[:12]}.webp"
    output_path = AVATAR_UPLOAD_DIR / final_name

    try:
        file.stream.seek(0)
        optimize_and_save_avatar(file, output_path)
    except Exception:
        return jsonify({"error": "No se pudo procesar la imagen. Intenta con otro archivo."}), 400

    return jsonify(
        {
            "message": "Imagen subida y optimizada correctamente.",
            "avatar": f"uploads/{final_name}",
            "avatar_url": url_for("static", filename=f"img/uploads/{final_name}"),
        }
    )


@app.route("/api/admin/barberos", methods=["POST"])
@role_required("admin")
def api_admin_barberos_create():
    data = get_payload()

    nombre = data.get("nombre", "").strip()
    telefono = normalize_phone_10(data.get("telefono", ""))
    email = data.get("email", "").strip().lower() or None
    avatar = normalize_avatar_name(data.get("avatar", DEFAULT_AVATAR))
    username = data.get("username", "").strip()
    password_temporal = data.get("password_temporal", "").strip()
    password_confirmacion = data.get("password_confirmacion", "").strip()
    dias_semana = parse_days_input(data.get("dias_semana", []))

    if not nombre or not telefono or not email or not username or not password_temporal or not password_confirmacion:
        return jsonify({"error": "Nombre, teléfono, correo, usuario y contraseña son obligatorios."}), 400

    if password_temporal != password_confirmacion:
        return jsonify({"error": "La confirmación de contraseña no coincide."}), 400

    pwd_error = validate_password_strength(password_temporal)
    if pwd_error:
        return jsonify({"error": pwd_error}), 400

    if email and Barbero.query.filter(Barbero.email == email).first():
        return jsonify({"error": "Ya existe un barbero con ese email."}), 409

    if not dias_semana:
        dias_semana = [1, 2, 3, 4, 5]

    try:
        hora_inicio = parse_time(data.get("hora_inicio", "09:00"))
        hora_fin = parse_time(data.get("hora_fin", "18:00"))
    except ValueError:
        return jsonify({"error": "Formato de hora inválido. Usa HH:MM."}), 400

    if hora_fin <= hora_inicio:
        return jsonify({"error": "La hora fin debe ser mayor que la hora inicio."}), 400

    barbero = Barbero(nombre=nombre, telefono=telefono, email=email, avatar=avatar, activo=True)
    db.session.add(barbero)
    db.session.flush()

    assign_barbero_to_active_servicios(barbero)

    set_barbero_horarios(barbero.id, dias_semana, hora_inicio, hora_fin)

    if User.query.filter_by(username=username).first():
        db.session.rollback()
        return jsonify({"error": "El username ya existe. Elige otro."}), 409

    user = User(username=username, role="barbero", barbero_id=barbero.id, activo=True)
    user.set_password(password_temporal)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Barbero creado correctamente.",
        "barbero": serialize_barbero(barbero),
        "credenciales": {"username": username, "password_temporal": password_temporal},
    }), 201


@app.route("/api/admin/barberos/<int:barbero_id>", methods=["PUT"])
@role_required("admin")
def api_admin_barberos_update(barbero_id):
    barbero = db.session.get(Barbero, barbero_id)
    if not barbero:
        return jsonify({"error": "Barbero no encontrado."}), 404

    data = get_payload()
    nombre = data.get("nombre", barbero.nombre).strip()
    telefono = normalize_phone_10(data.get("telefono", barbero.telefono or ""))
    email = data.get("email", barbero.email or "").strip().lower() or None
    avatar = normalize_avatar_name(data.get("avatar", barbero.avatar or DEFAULT_AVATAR))

    if not nombre or not telefono:
        return jsonify({"error": "Nombre y teléfono son obligatorios."}), 400

    if not email:
        return jsonify({"error": "El correo es obligatorio."}), 400

    existing_email_owner = Barbero.query.filter(Barbero.email == email, Barbero.id != barbero_id).first() if email else None
    if existing_email_owner:
        return jsonify({"error": "Ya existe otro barbero con ese email."}), 409

    barbero.nombre = nombre
    barbero.telefono = telefono
    barbero.email = email
    barbero.avatar = avatar

    dias_data = data.get("dias_semana")
    if dias_data is not None:
        dias_semana = parse_days_input(dias_data)
        if not dias_semana:
            return jsonify({"error": "Debes enviar al menos un día de trabajo (1..7)."}), 400

        try:
            hora_inicio = parse_time(data.get("hora_inicio", "09:00"))
            hora_fin = parse_time(data.get("hora_fin", "18:00"))
        except ValueError:
            return jsonify({"error": "Formato de hora inválido. Usa HH:MM."}), 400

        if hora_fin <= hora_inicio:
            return jsonify({"error": "La hora fin debe ser mayor que la hora inicio."}), 400

        set_barbero_horarios(barbero.id, dias_semana, hora_inicio, hora_fin)

    user = User.query.filter_by(barbero_id=barbero.id).first()
    if user:
        username = data.get("username", "").strip()
        password_temporal = data.get("password_temporal", "").strip()
        password_confirmacion = data.get("password_confirmacion", "").strip()

        if not username:
            return jsonify({"error": "El usuario es obligatorio."}), 400

        if username and username != user.username:
            if User.query.filter(User.username == username, User.id != user.id).first():
                return jsonify({"error": "El username ya existe. Elige otro."}), 409
            user.username = username

        if password_temporal:
            if password_temporal != password_confirmacion:
                return jsonify({"error": "La confirmación de contraseña no coincide."}), 400

            pwd_error = validate_password_strength(password_temporal)
            if pwd_error:
                return jsonify({"error": pwd_error}), 400

            user.set_password(password_temporal)

    db.session.commit()
    return jsonify({"message": "Barbero actualizado correctamente.", "barbero": serialize_barbero(barbero)})


@app.route("/api/admin/barberos/<int:barbero_id>", methods=["DELETE"])
@role_required("admin")
def api_admin_barberos_delete(barbero_id):
    barbero = db.session.get(Barbero, barbero_id)
    if not barbero:
        return jsonify({"error": "Barbero no encontrado."}), 404

    mode = request.args.get("mode", "deactivate").strip().lower()

    if mode == "delete":
        has_citas = Cita.query.filter_by(barbero_id=barbero.id).first() is not None
        if has_citas:
            return jsonify({"error": "No se puede eliminar porque el barbero tiene citas. Puedes desactivarlo."}), 409

        HorarioBarbero.query.filter_by(barbero_id=barbero.id).delete()
        db.session.execute(servicio_barberos.delete().where(servicio_barberos.c.barbero_id == barbero.id))

        user = User.query.filter_by(barbero_id=barbero.id).first()
        if user:
            db.session.delete(user)

        db.session.delete(barbero)
        db.session.commit()
        return jsonify({"message": "Barbero eliminado correctamente."})

    barbero.activo = False
    HorarioBarbero.query.filter_by(barbero_id=barbero.id).update({"activo": False})

    user = User.query.filter_by(barbero_id=barbero.id).first()
    if user:
        user.activo = False

    db.session.commit()
    return jsonify({"message": "Barbero desactivado correctamente."})


@app.route("/api/admin/catalogo", methods=["GET"])
@role_required("admin")
def api_admin_catalogo_list():
    items = [serialize_producto(p) for p in ProductoInventario.query.order_by(ProductoInventario.id.asc()).all()]
    return jsonify(items)


@app.route("/api/admin/catalogo", methods=["POST"])
@role_required("admin")
def api_admin_catalogo_create():
    data = request.get_json(silent=True) or {}

    id_item = str(data.get("id_item", "")).strip()
    nombre = str(data.get("nombre", "")).strip()
    detalles = str(data.get("detalles", "")).strip()
    imagen = normalize_product_image_name(data.get("imagen"))

    try:
        precio = int(data.get("precio", 0))
        stock = int(data.get("stock", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Precio y stock deben ser números válidos."}), 400

    if not id_item or not nombre:
        return jsonify({"error": "ID_item y nombre son obligatorios."}), 400

    if precio < 0 or stock < 0:
        return jsonify({"error": "Precio y stock no pueden ser negativos."}), 400

    if ProductoInventario.query.filter_by(id_item=id_item).first():
        return jsonify({"error": "Ya existe un artículo con ese ID_item."}), 409

    item = ProductoInventario(
        id_item=id_item,
        nombre=nombre,
        detalles=detalles,
        imagen=imagen,
        precio=precio,
        stock=stock,
        activo=True,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Artículo registrado correctamente.", "item": serialize_producto(item)}), 201


@app.route("/api/admin/catalogo/<int:item_id>", methods=["PUT"])
@role_required("admin")
def api_admin_catalogo_update(item_id):
    item = db.session.get(ProductoInventario, item_id)
    if not item:
        return jsonify({"error": "Artículo no encontrado."}), 404

    data = request.get_json(silent=True) or {}
    id_item = str(data.get("id_item", item.id_item)).strip()
    nombre = str(data.get("nombre", item.nombre)).strip()
    detalles = str(data.get("detalles", item.detalles or "")).strip()
    imagen = normalize_product_image_name(data.get("imagen", item.imagen))

    try:
        precio = int(data.get("precio", item.precio))
        stock = int(data.get("stock", item.stock))
    except (TypeError, ValueError):
        return jsonify({"error": "Precio y stock deben ser números válidos."}), 400

    if not id_item or not nombre:
        return jsonify({"error": "ID_item y nombre son obligatorios."}), 400

    if precio < 0 or stock < 0:
        return jsonify({"error": "Precio y stock no pueden ser negativos."}), 400

    existing = ProductoInventario.query.filter(
        ProductoInventario.id_item == id_item,
        ProductoInventario.id != item.id,
    ).first()
    if existing:
        return jsonify({"error": "Ya existe otro artículo con ese ID_item."}), 409

    item.id_item = id_item
    item.nombre = nombre
    item.detalles = detalles
    item.imagen = imagen
    item.precio = precio
    item.stock = stock
    db.session.commit()
    return jsonify({"message": "Artículo actualizado correctamente.", "item": serialize_producto(item)})


@app.route("/api/admin/catalogo/imagen", methods=["POST"])
@role_required("admin")
def api_admin_catalogo_image_upload():
    file = request.files.get("imagen")
    if not file or not file.filename:
        return jsonify({"error": "Debes seleccionar una imagen."}), 400

    if not allowed_product_file(file.filename):
        return jsonify({"error": "Formato inválido. Usa PNG, JPG, JPEG o WEBP."}), 400

    PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    final_name = f"producto_{uuid4().hex[:12]}.{ext}"
    file.save(PRODUCT_UPLOAD_DIR / final_name)

    return jsonify(
        {
            "message": "Imagen de producto subida correctamente.",
            "imagen": f"uploads/{final_name}",
            "imagen_url": url_for("static", filename=f"img/uploads/{final_name}"),
        }
    )


@app.route("/api/admin/catalogo/<int:item_id>", methods=["DELETE"])
@role_required("admin")
def api_admin_catalogo_delete(item_id):
    item = db.session.get(ProductoInventario, item_id)
    if not item:
        return jsonify({"error": "Artículo no encontrado."}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Artículo eliminado correctamente."})


@app.route("/api/portafolio", methods=["GET"])
def api_portafolio_public_list():
    barbero_id = request.args.get("barbero_id", type=int)
    if barbero_id:
        barbero = db.session.get(Barbero, barbero_id)
        if not barbero or not barbero.activo:
            return jsonify([])
        items = [
            serialize_portfolio_image(p)
            for p in get_portfolio_items_ordered(
                only_active=True,
                barbero_scope="barber",
                barbero_id=barbero_id,
            )
        ]
        return jsonify(items)

    items = [
        serialize_portfolio_image(p)
        for p in get_portfolio_items_ordered(only_active=True, barbero_scope="global")
    ]
    return jsonify(items)


@app.route("/api/admin/portafolio", methods=["GET"])
@role_required("admin")
def api_admin_portafolio_list():
    scope = str(request.args.get("scope", "global")).strip().lower()
    barbero_id = request.args.get("barbero_id", type=int)

    if scope == "barbero":
        if not barbero_id:
            return jsonify([])
        items = [
            serialize_portfolio_image(p)
            for p in get_portfolio_items_ordered(
                only_active=False,
                barbero_scope="barber",
                barbero_id=barbero_id,
            )
        ]
    elif scope == "all":
        items = [serialize_portfolio_image(p) for p in get_portfolio_items_ordered(only_active=False, barbero_scope="all")]
    else:
        items = [
            serialize_portfolio_image(p)
            for p in get_portfolio_items_ordered(only_active=False, barbero_scope="global")
        ]
    return jsonify(items)


@app.route("/api/admin/portafolio", methods=["POST"])
@role_required("admin")
def api_admin_portafolio_create():
    file = request.files.get("imagen")
    if not file or not file.filename:
        return jsonify({"error": "Debes seleccionar una imagen."}), 400

    if not allowed_portfolio_file(file.filename):
        return jsonify({"error": "Formato inválido. Usa PNG, JPG, JPEG o WEBP."}), 400

    raw_barbero_id = str(request.form.get("barbero_id", "")).strip()
    target_barbero_id = None
    target_scope = "global"
    if raw_barbero_id:
        try:
            target_barbero_id = int(raw_barbero_id)
        except ValueError:
            return jsonify({"error": "barbero_id inválido."}), 400

        barbero = db.session.get(Barbero, target_barbero_id)
        if not barbero:
            return jsonify({"error": "Barbero no encontrado."}), 404
        target_scope = "barber"

    PORTFOLIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    final_name = f"portfolio_{uuid4().hex[:12]}.{ext}"
    file.save(PORTFOLIO_UPLOAD_DIR / final_name)

    item = PortfolioImagen(
        imagen=final_name,
        barbero_id=target_barbero_id,
        sort_order=get_next_portfolio_order(target_scope, target_barbero_id),
        activo=True,
    )
    db.session.add(item)
    db.session.commit()
    normalize_portfolio_order(target_scope, target_barbero_id)

    return jsonify({"message": "Imagen agregada al portafolio.", "item": serialize_portfolio_image(item)}), 201


@app.route("/api/admin/portafolio/<int:image_id>", methods=["DELETE"])
@role_required("admin")
def api_admin_portafolio_delete(image_id):
    item = db.session.get(PortfolioImagen, image_id)
    if not item:
        return jsonify({"error": "Imagen no encontrada."}), 404

    image_path = PORTFOLIO_UPLOAD_DIR / item.imagen
    if item.imagen and image_path.exists() and image_path.is_file():
        image_path.unlink(missing_ok=True)

    scope = "barber" if item.barbero_id is not None else "global"
    scope_barbero_id = item.barbero_id

    db.session.delete(item)
    db.session.commit()
    normalize_portfolio_order(scope, scope_barbero_id)
    return jsonify({"message": "Imagen eliminada del portafolio."})


@app.route("/api/admin/portafolio/<int:image_id>/orden", methods=["PATCH"])
@role_required("admin")
def api_admin_portafolio_reorder(image_id):
    item = db.session.get(PortfolioImagen, image_id)
    if not item:
        return jsonify({"error": "Imagen no encontrada."}), 404

    data = request.get_json(silent=True) or {}
    direction = str(data.get("direction", "")).strip().lower()
    if direction not in {"up", "down"}:
        return jsonify({"error": "Dirección inválida. Usa up o down."}), 400

    scope = "barber" if item.barbero_id is not None else "global"
    scope_barbero_id = item.barbero_id

    normalize_portfolio_order(scope, scope_barbero_id)
    items = get_portfolio_items_ordered(
        only_active=False,
        barbero_scope=scope,
        barbero_id=scope_barbero_id,
    )
    current_idx = next((i for i, row in enumerate(items) if row.id == item.id), None)
    if current_idx is None:
        return jsonify({"error": "Imagen no encontrada en el orden actual."}), 404

    target_idx = current_idx - 1 if direction == "up" else current_idx + 1
    if target_idx < 0 or target_idx >= len(items):
        return jsonify({"error": "No se puede mover más en esa dirección."}), 400

    current_item = items[current_idx]
    target_item = items[target_idx]
    current_item.sort_order, target_item.sort_order = target_item.sort_order, current_item.sort_order
    db.session.commit()
    normalize_portfolio_order(scope, scope_barbero_id)

    return jsonify({"message": "Orden del portafolio actualizado."})


@app.route("/api/barbero/portafolio", methods=["GET"])
@role_required("barbero")
def api_barbero_portafolio_list():
    barbero_id = current_user.barbero_id
    items = [
        serialize_portfolio_image(p)
        for p in get_portfolio_items_ordered(
            only_active=False,
            barbero_scope="barber",
            barbero_id=barbero_id,
        )
    ]
    return jsonify(items)


@app.route("/api/barbero/portafolio", methods=["POST"])
@role_required("barbero")
def api_barbero_portafolio_create():
    file = request.files.get("imagen")
    if not file or not file.filename:
        return jsonify({"error": "Debes seleccionar una imagen."}), 400

    if not allowed_portfolio_file(file.filename):
        return jsonify({"error": "Formato inválido. Usa PNG, JPG, JPEG o WEBP."}), 400

    PORTFOLIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    final_name = f"portfolio_{uuid4().hex[:12]}.{ext}"
    file.save(PORTFOLIO_UPLOAD_DIR / final_name)

    barbero_id = current_user.barbero_id
    item = PortfolioImagen(
        imagen=final_name,
        barbero_id=barbero_id,
        sort_order=get_next_portfolio_order("barber", barbero_id),
        activo=True,
    )
    db.session.add(item)
    db.session.commit()
    normalize_portfolio_order("barber", barbero_id)

    return jsonify({"message": "Imagen agregada a tu portafolio.", "item": serialize_portfolio_image(item)}), 201


@app.route("/api/barbero/portafolio/<int:image_id>", methods=["DELETE"])
@role_required("barbero")
def api_barbero_portafolio_delete(image_id):
    item = db.session.get(PortfolioImagen, image_id)
    if not item or item.barbero_id != current_user.barbero_id:
        return jsonify({"error": "Imagen no encontrada."}), 404

    image_path = PORTFOLIO_UPLOAD_DIR / item.imagen
    if item.imagen and image_path.exists() and image_path.is_file():
        image_path.unlink(missing_ok=True)

    db.session.delete(item)
    db.session.commit()
    normalize_portfolio_order("barber", current_user.barbero_id)
    return jsonify({"message": "Imagen eliminada de tu portafolio."})


@app.route("/api/barbero/portafolio/<int:image_id>/orden", methods=["PATCH"])
@role_required("barbero")
def api_barbero_portafolio_reorder(image_id):
    item = db.session.get(PortfolioImagen, image_id)
    if not item or item.barbero_id != current_user.barbero_id:
        return jsonify({"error": "Imagen no encontrada."}), 404

    data = request.get_json(silent=True) or {}
    direction = str(data.get("direction", "")).strip().lower()
    if direction not in {"up", "down"}:
        return jsonify({"error": "Dirección inválida. Usa up o down."}), 400

    barbero_id = current_user.barbero_id
    normalize_portfolio_order("barber", barbero_id)
    items = get_portfolio_items_ordered(
        only_active=False,
        barbero_scope="barber",
        barbero_id=barbero_id,
    )

    current_idx = next((i for i, row in enumerate(items) if row.id == item.id), None)
    if current_idx is None:
        return jsonify({"error": "Imagen no encontrada en el orden actual."}), 404

    target_idx = current_idx - 1 if direction == "up" else current_idx + 1
    if target_idx < 0 or target_idx >= len(items):
        return jsonify({"error": "No se puede mover más en esa dirección."}), 400

    current_item = items[current_idx]
    target_item = items[target_idx]
    current_item.sort_order, target_item.sort_order = target_item.sort_order, current_item.sort_order
    db.session.commit()
    normalize_portfolio_order("barber", barbero_id)

    return jsonify({"message": "Orden de tu portafolio actualizado."})


def can_manage_cita(cita):
    if current_user.role == "admin":
        return True
    return current_user.role == "barbero" and cita.barbero_id == current_user.barbero_id


@app.route("/api/citas/<int:cita_id>/accion", methods=["PATCH"])
@role_required("admin", "barbero")
def api_citas_accion(cita_id):
    cita = db.session.get(Cita, cita_id)
    if not cita:
        return jsonify({"error": "Cita no encontrada."}), 404

    if not can_manage_cita(cita):
        return jsonify({"error": "No tienes permisos para modificar esta cita."}), 403

    data = get_payload()
    accion = data.get("accion", "").strip().lower()

    if accion in {"confirmar", "completar", "cancelar"}:
        estado_map = {"confirmar": "confirmada", "completar": "completada", "cancelar": "cancelada"}
        cita.estado = estado_map[accion]
        db.session.commit()
        return jsonify({"message": f"Cita {cita.estado} correctamente.", "cita": serialize_cita(cita)})

    return jsonify({"error": "Acción no válida."}), 400


@app.route("/api/admin/citas/<int:cita_id>", methods=["DELETE"])
@role_required("admin")
def api_admin_citas_delete(cita_id):
    cita = db.session.get(Cita, cita_id)
    if not cita:
        return jsonify({"error": "Cita no encontrada."}), 404

    if cita.estado != "cancelada":
        return jsonify({"error": "Solo se pueden eliminar citas canceladas."}), 400

    db.session.delete(cita)
    db.session.commit()
    return jsonify({"message": "Cita cancelada eliminada del historial."})


@app.route("/citas/cancelar/<string:token>", methods=["GET", "POST"])
def public_cancel_cita(token):
    cita = Cita.query.filter_by(cancel_token=token.strip()).first()
    if not cita:
        return render_template(
            "cancel_cita.html",
            cita=None,
            cancel_token=token,
            cancel_state="not_found",
        ), 404

    if request.method == "POST":
        if cita.estado == "completada":
            return render_template(
                "cancel_cita.html",
                cita=cita,
                cancel_token=token,
                cancel_state="completed",
            ), 400

        if cita.estado != "cancelada":
            cita.estado = "cancelada"
            cita.canceled_at = datetime.utcnow()
            db.session.commit()

        return render_template(
            "cancel_cita.html",
            cita=cita,
            cancel_token=token,
            cancel_state="cancelled",
        )

    if cita.estado == "cancelada":
        cancel_state = "already_cancelled"
    elif cita.estado == "completada":
        cancel_state = "completed"
    else:
        cancel_state = "ready"

    return render_template(
        "cancel_cita.html",
        cita=cita,
        cancel_token=token,
        cancel_state=cancel_state,
    )


@app.route("/api/barbero/servicio", methods=["GET"])
@role_required("barbero")
def api_barbero_servicio_get():
    barbero = db.session.get(Barbero, current_user.barbero_id)
    if not barbero:
        return jsonify({"error": "No se encontró el perfil del barbero."}), 404

    today = date.today()
    excepciones = (
        ExcepcionDisponibilidadBarbero.query
        .filter(ExcepcionDisponibilidadBarbero.barbero_id == barbero.id)
        .filter(ExcepcionDisponibilidadBarbero.fecha >= today)
        .order_by(ExcepcionDisponibilidadBarbero.fecha.asc(), ExcepcionDisponibilidadBarbero.id.asc())
        .all()
    )

    return jsonify(
        {
            "barbero": serialize_barbero(barbero),
            "excepciones": [serialize_barbero_excepcion(e) for e in excepciones],
        }
    )


@app.route("/api/barbero/servicio/perfil", methods=["PATCH"])
@role_required("barbero")
def api_barbero_servicio_perfil():
    barbero = db.session.get(Barbero, current_user.barbero_id)
    if not barbero:
        return jsonify({"error": "No se encontró el perfil del barbero."}), 404

    data = request.get_json(silent=True) or {}
    if "activo" not in data:
        return jsonify({"error": "Debes enviar el estado activo."}), 400

    barbero.activo = bool(data.get("activo"))
    db.session.commit()
    return jsonify({"message": "Estado del perfil actualizado.", "barbero": serialize_barbero(barbero)})


@app.route("/api/barbero/servicio/descanso", methods=["POST"])
@role_required("barbero")
def api_barbero_servicio_descanso():
    barbero = db.session.get(Barbero, current_user.barbero_id)
    if not barbero:
        return jsonify({"error": "No se encontró el perfil del barbero."}), 404

    data = request.get_json(silent=True) or {}
    fecha_inicio_str = str(data.get("fecha_inicio", "")).strip()
    fecha_fin_str = str(data.get("fecha_fin", fecha_inicio_str)).strip()
    motivo = str(data.get("motivo", "")).strip()[:255]

    if not fecha_inicio_str:
        return jsonify({"error": "Debes enviar fecha_inicio."}), 400

    try:
        fecha_inicio = parse_date(fecha_inicio_str)
        fecha_fin = parse_date(fecha_fin_str)
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Usa YYYY-MM-DD."}), 400

    if fecha_fin < fecha_inicio:
        return jsonify({"error": "fecha_fin no puede ser menor a fecha_inicio."}), 400

    delta_days = (fecha_fin - fecha_inicio).days
    if delta_days > 60:
        return jsonify({"error": "El rango máximo permitido es de 60 días."}), 400

    current_date = fecha_inicio
    while current_date <= fecha_fin:
        ExcepcionDisponibilidadBarbero.query.filter_by(barbero_id=barbero.id, fecha=current_date).delete()
        db.session.add(
            ExcepcionDisponibilidadBarbero(
                barbero_id=barbero.id,
                fecha=current_date,
                tipo="off",
                motivo=motivo or "Descanso",
                activo=True,
            )
        )
        current_date += timedelta(days=1)

    db.session.commit()
    return jsonify({"message": "Descanso aplicado correctamente."}), 201


@app.route("/api/barbero/servicio/horario-temporal", methods=["POST"])
@role_required("barbero")
def api_barbero_servicio_horario_temporal():
    barbero = db.session.get(Barbero, current_user.barbero_id)
    if not barbero:
        return jsonify({"error": "No se encontró el perfil del barbero."}), 404

    data = request.get_json(silent=True) or {}
    fecha_inicio_str = str(data.get("fecha_inicio", "")).strip()
    fecha_fin_str = str(data.get("fecha_fin", fecha_inicio_str)).strip()
    hora_inicio_str = str(data.get("hora_inicio", "")).strip()
    hora_fin_str = str(data.get("hora_fin", "")).strip()
    motivo = str(data.get("motivo", "")).strip()[:255]

    if not fecha_inicio_str or not hora_inicio_str or not hora_fin_str:
        return jsonify({"error": "Debes enviar fecha_inicio, hora_inicio y hora_fin."}), 400

    try:
        fecha_inicio = parse_date(fecha_inicio_str)
        fecha_fin = parse_date(fecha_fin_str)
        hora_inicio = parse_time(hora_inicio_str)
        hora_fin = parse_time(hora_fin_str)
    except ValueError:
        return jsonify({"error": "Formato inválido en fechas u horas."}), 400

    if fecha_fin < fecha_inicio:
        return jsonify({"error": "fecha_fin no puede ser menor a fecha_inicio."}), 400
    if hora_fin <= hora_inicio:
        return jsonify({"error": "hora_fin debe ser mayor que hora_inicio."}), 400

    delta_days = (fecha_fin - fecha_inicio).days
    if delta_days > 60:
        return jsonify({"error": "El rango máximo permitido es de 60 días."}), 400

    current_date = fecha_inicio
    while current_date <= fecha_fin:
        ExcepcionDisponibilidadBarbero.query.filter_by(barbero_id=barbero.id, fecha=current_date).delete()
        db.session.add(
            ExcepcionDisponibilidadBarbero(
                barbero_id=barbero.id,
                fecha=current_date,
                tipo="horario",
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                motivo=motivo or "Horario temporal",
                activo=True,
            )
        )
        current_date += timedelta(days=1)

    db.session.commit()
    return jsonify({"message": "Horario temporal aplicado correctamente."}), 201


@app.route("/api/barbero/servicio/excepcion/<int:excepcion_id>", methods=["DELETE"])
@role_required("barbero")
def api_barbero_servicio_excepcion_delete(excepcion_id):
    excepcion = db.session.get(ExcepcionDisponibilidadBarbero, excepcion_id)
    if not excepcion or excepcion.barbero_id != current_user.barbero_id:
        return jsonify({"error": "Excepción no encontrada."}), 404

    db.session.delete(excepcion)
    db.session.commit()
    return jsonify({"message": "Configuración eliminada correctamente."})


@app.route("/api/admin/estadisticas/clientes", methods=["GET"])
@role_required("admin")
def api_estadisticas_clientes():
    """Estadísticas de clientes y citas para dashboard."""
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    # Obtener todas las citas
    citas = Cita.query.order_by(Cita.fecha.asc()).all()
    
    # Estadísticas generales
    total_clientes = Cliente.query.count()
    total_citas = len(citas)
    citas_confirmadas = sum(1 for c in citas if c.estado == 'confirmada')
    citas_canceladas = sum(1 for c in citas if c.estado == 'cancelada')
    
    # Citas por día de la semana (últimos 30 días)
    today = date.today()
    hace_30_dias = today - timedelta(days=30)
    dias_semana_count = defaultdict(int)
    dias_semana_nombres = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    
    for cita in citas:
        if hace_30_dias <= cita.fecha <= today:
            dia_semana = cita.fecha.weekday()
            dias_semana_count[dia_semana] += 1
    
    dias_activos = [{"dia": dias_semana_nombres[i], "count": dias_semana_count.get(i, 0)} for i in range(7)]
    
    # Citas por mes (últimos 12 meses)
    hace_12_meses = today - timedelta(days=365)
    meses_count = defaultdict(int)
    meses_nombres = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 
                     7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
    
    for cita in citas:
        if hace_12_meses <= cita.fecha <= today:
            mes_key = (cita.fecha.year, cita.fecha.month)
            meses_count[mes_key] += 1
    
    meses_data = []
    for i in range(11, -1, -1):
        mes_date = today - timedelta(days=30 * i)
        mes_key = (mes_date.year, mes_date.month)
        count = meses_count.get(mes_key, 0)
        mes_label = f"{meses_nombres[mes_date.month]}"
        meses_data.append({"mes": mes_label, "count": count, "fecha": mes_key})
    
    # Clientes por semana (últimos 30 días)
    semanas_count = defaultdict(int)
    for cita in citas:
        if hace_30_dias <= cita.fecha <= today:
            semana_inicio = cita.fecha - timedelta(days=cita.fecha.weekday())
            semana_key = semana_inicio.isoformat()
            semanas_count[semana_key] += 1
    
    semanas_data = [{"semana": k, "count": v} for k, v in sorted(semanas_count.items())]
    
    # Historial reciente de citas (últimas 20)
    citas_recientes = []
    for cita in sorted(citas, key=lambda c: c.fecha, reverse=True)[:20]:
        cliente_nombre = f"{cita.cliente.nombres} {cita.cliente.apellidos}".strip() if cita.cliente else "Cliente"
        barbero_nombre = cita.barbero.nombre if cita.barbero else "Barbero"
        servicio_nombre = cita.servicio.nombre if cita.servicio else "Servicio"
        citas_recientes.append({
            "id": cita.id,
            "cliente": cliente_nombre,
            "barbero": barbero_nombre,
            "servicio": servicio_nombre,
            "fecha": cita.fecha.isoformat(),
            "hora": cita.hora_inicio.strftime("%H:%M"),
            "estado": cita.estado,
        })
    
    return jsonify({
        "total_clientes": total_clientes,
        "total_citas": total_citas,
        "citas_confirmadas": citas_confirmadas,
        "citas_canceladas": citas_canceladas,
        "dias_activos": dias_activos,
        "meses_data": meses_data,
        "semanas_data": semanas_data,
        "citas_recientes": citas_recientes,
    })


with app.app_context():
    if should_bootstrap():
        db.create_all()
        ensure_product_image_column()
        ensure_portfolio_table()
        ensure_barbero_service_tables()
        ensure_cita_public_columns()
        seed_data()
    else:
        ensure_product_image_column()
        ensure_portfolio_table()
        ensure_barbero_service_tables()
        ensure_cita_public_columns()

    ensure_sample_products()
    sync_service_catalog(reset_citas_on_change=True)
    ensure_admin_from_env()


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8000, use_reloader=False)
