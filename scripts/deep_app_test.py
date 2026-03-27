import io
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BASE_DIR / "instance" / "deep_integration_test.db"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class DeepAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

        os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
        os.environ["AUTO_BOOTSTRAP_DB"] = "1"

        import app as app_module

        cls.app_module = app_module
        cls.app = app_module.app
        cls.app.config["TESTING"] = True
        cls.db = app_module.db

    def setUp(self):
        self.client = self.app.test_client()
        self.admin_client = self.app.test_client()
        self.barber_client = self.app.test_client()
        self._reset_state()

    def _reset_state(self):
        m = self.app_module
        with self.app.app_context():
            m.Cita.query.delete()
            m.ExcepcionDisponibilidadBarbero.query.delete()

            for barbero in m.Barbero.query.all():
                barbero.activo = True

            self.db.session.commit()

            for item in m.ProductoInventario.query.filter(m.ProductoInventario.id_item.like("TEST-%")).all():
                self.db.session.delete(item)
            self.db.session.commit()

            for p in m.PortfolioImagen.query.filter(m.PortfolioImagen.imagen.like("portfolio_%")).all():
                image_path = m.PORTFOLIO_UPLOAD_DIR / p.imagen
                if image_path.exists():
                    image_path.unlink(missing_ok=True)
                self.db.session.delete(p)
            self.db.session.commit()

    def _login(self, client, username, password):
        response = client.post(
            "/login",
            data={
                "username": username,
                "password": password,
            },
            follow_redirects=False,
        )
        self.assertIn(response.status_code, (302, 303), f"Login fallido para {username}: {response.status_code}")

    def _get_service_and_barber(self):
        m = self.app_module
        with self.app.app_context():
            servicio = m.Servicio.query.filter_by(activo=True).first()
            self.assertIsNotNone(servicio, "No hay servicios activos")
            self.assertTrue(servicio.barberos, "El servicio no tiene barberos asignados")
            barbero = next((b for b in servicio.barberos if b.activo), None)
            self.assertIsNotNone(barbero, "No hay barberos activos para el servicio")
            return servicio.id, barbero.id

    def _find_available_slot(self, servicio_id, barbero_id, days_ahead=21):
        for offset in range(1, days_ahead + 1):
            fecha = (date.today() + timedelta(days=offset)).isoformat()
            resp = self.client.get(f"/api/disponibilidad?servicio_id={servicio_id}&fecha={fecha}")
            if resp.status_code != 200:
                continue
            data = resp.get_json()
            slots = data.get("slots", {}).get(str(barbero_id), [])
            if slots:
                return fecha, slots[0]
        self.fail("No se encontró disponibilidad para probar dentro del rango")

    def _create_public_booking(self, servicio_id, barbero_id, fecha, hora_inicio):
        payload = {
            "nombres": "Test",
            "apellidos": "Integracion",
            "telefono": "2225060172",
            "email": "test.integration@example.com",
            "servicio_id": servicio_id,
            "barbero_id": barbero_id,
            "fecha": fecha,
            "hora_inicio": hora_inicio,
        }
        return self.client.post("/api/citas/public", json=payload)

    def test_01_pages_load(self):
        home = self.client.get("/")
        login = self.client.get("/login")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(login.status_code, 200)

    def test_02_public_booking_removes_slot(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        fecha, slot = self._find_available_slot(servicio_id, barbero_id)

        create_resp = self._create_public_booking(servicio_id, barbero_id, fecha, slot)
        self.assertEqual(create_resp.status_code, 201, create_resp.get_data(as_text=True))

        disp_after = self.client.get(f"/api/disponibilidad?servicio_id={servicio_id}&fecha={fecha}")
        self.assertEqual(disp_after.status_code, 200)
        slots_after = disp_after.get_json().get("slots", {}).get(str(barbero_id), [])
        self.assertNotIn(slot, slots_after)

    def test_03_batch_conflict_same_time(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        fecha, slot = self._find_available_slot(servicio_id, barbero_id)

        payload = {
            "nombres": "Test",
            "apellidos": "Batch",
            "telefono": "2225060172",
            "email": "test.batch@example.com",
            "items": [
                {
                    "servicio_id": servicio_id,
                    "barbero_id": barbero_id,
                    "fecha": fecha,
                    "hora_inicio": slot,
                },
                {
                    "servicio_id": servicio_id,
                    "barbero_id": barbero_id,
                    "fecha": fecha,
                    "hora_inicio": slot,
                },
            ],
        }

        resp = self.client.post("/api/citas/public/lote", json=payload)
        self.assertEqual(resp.status_code, 409)

    def test_04_admin_cancel_and_delete_canceled_booking(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        fecha, slot = self._find_available_slot(servicio_id, barbero_id)
        create_resp = self._create_public_booking(servicio_id, barbero_id, fecha, slot)
        self.assertEqual(create_resp.status_code, 201)
        cita_id = create_resp.get_json()["cita"]["id"]

        self._login(self.admin_client, "admin", "admin123")

        cancel_resp = self.admin_client.patch(f"/api/citas/{cita_id}/accion", json={"accion": "cancelar"})
        self.assertEqual(cancel_resp.status_code, 200, cancel_resp.get_data(as_text=True))

        delete_resp = self.admin_client.delete(f"/api/admin/citas/{cita_id}")
        self.assertEqual(delete_resp.status_code, 200, delete_resp.get_data(as_text=True))

        all_citas = self.admin_client.get("/api/citas").get_json()
        self.assertFalse(any(int(c["id"]) == int(cita_id) for c in all_citas))

    def test_05_catalog_admin_crud(self):
        self._login(self.admin_client, "admin", "admin123")

        create_payload = {
            "id_item": "TEST-ITEM-001",
            "nombre": "Producto Test",
            "detalles": "Detalle de prueba",
            "precio": 123,
            "stock": 4,
        }
        create_resp = self.admin_client.post("/api/admin/catalogo", json=create_payload)
        self.assertEqual(create_resp.status_code, 201, create_resp.get_data(as_text=True))
        item_id = create_resp.get_json()["item"]["id"]

        update_resp = self.admin_client.put(
            f"/api/admin/catalogo/{item_id}",
            json={
                "id_item": "TEST-ITEM-001",
                "nombre": "Producto Test Editado",
                "detalles": "Detalle editado",
                "precio": 150,
                "stock": 8,
            },
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.get_data(as_text=True))

        delete_resp = self.admin_client.delete(f"/api/admin/catalogo/{item_id}")
        self.assertEqual(delete_resp.status_code, 200)

    def test_06_portfolio_admin_upload_reorder_delete(self):
        self._login(self.admin_client, "admin", "admin123")

        def upload(name):
            data = {
                "imagen": (io.BytesIO(b"fake-image-content"), name),
            }
            return self.admin_client.post("/api/admin/portafolio", data=data, content_type="multipart/form-data")

        up1 = upload("one.jpg")
        up2 = upload("two.jpg")
        self.assertEqual(up1.status_code, 201, up1.get_data(as_text=True))
        self.assertEqual(up2.status_code, 201, up2.get_data(as_text=True))

        id1 = up1.get_json()["item"]["id"]
        id2 = up2.get_json()["item"]["id"]

        move_resp = self.admin_client.patch(f"/api/admin/portafolio/{id2}/orden", json={"direction": "up"})
        self.assertEqual(move_resp.status_code, 200, move_resp.get_data(as_text=True))

        listado = self.admin_client.get("/api/admin/portafolio").get_json()
        ids = [r["id"] for r in listado[:2]]
        self.assertIn(id1, ids)
        self.assertIn(id2, ids)

        del1 = self.admin_client.delete(f"/api/admin/portafolio/{id1}")
        del2 = self.admin_client.delete(f"/api/admin/portafolio/{id2}")
        self.assertEqual(del1.status_code, 200)
        self.assertEqual(del2.status_code, 200)

    def test_07_barber_day_off_affects_disponibilidad(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        fecha, _ = self._find_available_slot(servicio_id, barbero_id)

        self._login(self.barber_client, "barbero1", "temp123")
        descanso_resp = self.barber_client.post(
            "/api/barbero/servicio/descanso",
            json={
                "fecha_inicio": fecha,
                "fecha_fin": fecha,
                "motivo": "prueba descanso",
            },
        )
        self.assertEqual(descanso_resp.status_code, 201, descanso_resp.get_data(as_text=True))

        disp = self.client.get(f"/api/disponibilidad?servicio_id={servicio_id}&fecha={fecha}").get_json()
        slots = disp.get("slots", {}).get(str(barbero_id), [])
        self.assertEqual(slots, [])

    def test_08_barber_profile_deactivate_hides_in_booking(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        fecha = (date.today() + timedelta(days=1)).isoformat()

        self._login(self.barber_client, "barbero1", "temp123")
        off_resp = self.barber_client.patch("/api/barbero/servicio/perfil", json={"activo": False})
        self.assertEqual(off_resp.status_code, 200, off_resp.get_data(as_text=True))

        disp = self.client.get(f"/api/disponibilidad?servicio_id={servicio_id}&fecha={fecha}")
        self.assertEqual(disp.status_code, 200)
        ids = [int(b["id"]) for b in disp.get_json().get("barberos", [])]
        self.assertNotIn(int(barbero_id), ids)

    def test_09_barber_temporary_schedule_limits_slots(self):
        servicio_id, barbero_id = self._get_service_and_barber()
        target_date = (date.today() + timedelta(days=2)).isoformat()

        self._login(self.barber_client, "barbero1", "temp123")
        temp_resp = self.barber_client.post(
            "/api/barbero/servicio/horario-temporal",
            json={
                "fecha_inicio": target_date,
                "fecha_fin": target_date,
                "hora_inicio": "12:00",
                "hora_fin": "14:00",
                "motivo": "prueba horario temporal",
            },
        )
        self.assertEqual(temp_resp.status_code, 201, temp_resp.get_data(as_text=True))

        disp = self.client.get(f"/api/disponibilidad?servicio_id={servicio_id}&fecha={target_date}")
        self.assertEqual(disp.status_code, 200)
        slots = disp.get_json().get("slots", {}).get(str(barbero_id), [])

        for slot in slots:
            h, m = map(int, slot.split(":"))
            minutes = h * 60 + m
            self.assertGreaterEqual(minutes, 12 * 60)
            self.assertLess(minutes, 14 * 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
