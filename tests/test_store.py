import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from ayudas import store

TODAY = date(2026, 10, 9)


def fake_detail(code):
    return {"codigoBDNS": code, "descripcion": f"Ayuda {code}", "organo": {"nivel1": "LOCAL", "nivel2": "OLIVA"},
            "fechaRecepcion": "2026-10-01", "fechaFinSolicitud": "2026-12-31", "presupuestoTotal": 1000,
            "sedeElectronica": "https//sede.oliva.es", "ignored_field": "x",
            "tiposBeneficiarios": [{"descripcion": "PERSONAS FÍSICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA"}],
            "regiones": [{"descripcion": "ES523 - Valencia / València"}],
            "sectores": [{"codigo": "G"}, {"codigo": "85.5"}],
            "documentos": [{"id": 7, "nombreFic": "bases.pdf", "long": 123}],
            "anuncios": [{"titulo": "Extracto", "datPublicacion": "2026-10-02", "desDiarioOficial": "BOP",
                          "url": "https://bop.example/1",
                          "texto": "<p>Primero. Personas beneficiarias</p><p>Vecinos empadronados en Oliva.</p>"
                                   "<p>Segundo. Objeto</p>"}]}


def quiet(*_):
    pass


class Slim(unittest.TestCase):
    def test_records_keep_only_digested_fields(self):
        record = store.slim(fake_detail("1"))
        self.assertNotIn("ignored_field", record)
        self.assertEqual(record["beneficiarios"], [1])
        self.assertEqual(record["regiones"], ["ES523"])
        self.assertEqual(record["sectores"], ["G", "Q"])
        self.assertEqual(record["documento"], {"id": 7, "nombre": "bases.pdf"})
        self.assertEqual(record["boletin"], {"url": "https://bop.example/1", "diario": "BOP"})
        self.assertEqual(record["publicacion"], "2026-10-02")
        self.assertEqual(record["quien"], "Vecinos empadronados en Oliva")
        self.assertEqual(record["sede"], "https://sede.oliva.es")

    def test_grants_named_for_one_entity_are_not_public(self):
        self.assertFalse(store.is_public("SUBVENCIÓN NOMINATIVA A LA ASOCIACIÓN X"))
        self.assertFalse(store.is_public("Convenio con el Ayuntamiento de Y"))
        self.assertTrue(store.is_public("Ayudas al alquiler para jóvenes"))


class Update(unittest.TestCase):
    def test_new_calls_are_added_once_and_keep_their_first_day(self):
        db = store.empty()
        search = lambda since, until: [{"numeroConvocatoria": "1", "descripcion": "Ayuda"},
                                       {"numeroConvocatoria": 2, "descripcion": "Ayuda"}]
        new = store.update(db, search, fake_detail, TODAY, horizon_days=10, log=quiet)
        self.assertEqual(sorted(new), ["1", "2"])
        self.assertEqual(store.update(db, search, fake_detail, TODAY + timedelta(days=1), horizon_days=10, log=quiet), [])
        self.assertEqual(db["calls"]["1"]["first_seen"], "2026-10-09")
        self.assertEqual(db["estado"]["actualizado"], "2026-10-10")

    def test_backfill_walks_back_to_the_horizon(self):
        windows = []

        def search(since, until):
            windows.append((since, until))
            return [{"numeroConvocatoria": f"{since:%m%d}", "descripcion": "Ayuda"}]

        db = store.empty()
        store.update(db, search, fake_detail, TODAY, horizon_days=30, log=quiet)
        self.assertEqual(db["estado"]["cubierto_desde"], "2026-09-09")
        self.assertEqual(windows[0], (TODAY - timedelta(days=10), TODAY))
        self.assertEqual(windows[1], (date(2026, 9, 19), date(2026, 9, 28)))
        self.assertEqual(len(windows), 3)

    def test_nominative_grants_are_never_downloaded(self):
        asked = []
        detail = lambda code: asked.append(code) or fake_detail(code)
        search = lambda *_: [{"numeroConvocatoria": "9", "descripcion": "Subvención nominativa a X"}]
        store.update(store.empty(), search, detail, TODAY, horizon_days=10, log=quiet)
        self.assertEqual(asked, [])

    def test_out_of_time_stops_and_the_next_run_carries_on(self):
        db = store.empty()
        search = lambda *_: [{"numeroConvocatoria": "1", "descripcion": "Ayuda"}]
        self.assertEqual(store.update(db, search, fake_detail, TODAY, budget_seconds=0, log=quiet), [])
        self.assertNotIn("cubierto_desde", db["estado"])
        self.assertEqual(store.update(db, search, fake_detail, TODAY, horizon_days=10, log=quiet), ["1"])

    def test_a_failing_record_does_not_stop_the_run(self):
        def flaky(code):
            if code == "bad":
                raise OSError("timeout")
            return fake_detail(code)
        found = lambda *_: [{"numeroConvocatoria": "bad", "descripcion": "x"}, {"numeroConvocatoria": "ok", "descripcion": "x"}]
        self.assertEqual(store.update(store.empty(), found, flaky, TODAY, horizon_days=10, log=quiet), ["ok"])


class Files(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        db = store.empty()
        store.update(db, lambda *_: [{"numeroConvocatoria": "1", "descripcion": "x"}], fake_detail, TODAY,
                     horizon_days=10, log=quiet)
        with tempfile.TemporaryDirectory() as folder:
            store.save(db, Path(folder))
            again = store.load(Path(folder))
        self.assertEqual(again["calls"], db["calls"])
        self.assertEqual(again["estado"], db["estado"])

    def test_long_closed_calls_are_forgotten(self):
        db = store.empty()
        store.update(db, lambda *_: [{"numeroConvocatoria": "1", "descripcion": "x"}], fake_detail, TODAY,
                     horizon_days=10, log=quiet)
        store.forget_old(db, date(2027, 2, 28))  # closed on 31 Dec, 59 days earlier
        self.assertIn("1", db["calls"])
        store.forget_old(db, date(2027, 3, 2))
        self.assertNotIn("1", db["calls"])


if __name__ == "__main__":
    unittest.main()
