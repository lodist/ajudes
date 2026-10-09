import unittest
from datetime import date

from ayudas import store


def fake_detail(code):
    return {"codigoBDNS": code, "organo": {"nivel1": "LOCAL", "nivel2": "OLIVA"}, "descripcion": f"Ayuda {code}",
            "fechaRecepcion": "2026-10-01", "fechaFinSolicitud": "2026-12-31", "ignored_field": "x",
            "documentos": [{"id": 7, "nombreFic": "bases.pdf", "long": 123}],
            "anuncios": [{"titulo": "Extracto", "texto": "<p>x</p>", "datPublicacion": "2026-10-02",
                          "desDiarioOficial": "BOP", "url": "https://bop.example/1", "cve": None}]}


def quiet(*_):
    pass


class Update(unittest.TestCase):
    def test_new_calls_are_added_once_and_keep_their_first_day(self):
        db = store.empty()
        search = lambda since, until: [{"numeroConvocatoria": "1"}, {"numeroConvocatoria": 2}]
        self.assertEqual(store.update(db, search, fake_detail, date(2026, 10, 9), 45, log=quiet), ["1", "2"])
        self.assertEqual(store.update(db, search, fake_detail, date(2026, 10, 10), 45, log=quiet), [])
        self.assertEqual(db["calls"]["1"]["first_seen"], "2026-10-09")
        self.assertEqual(db["calls"]["1"]["checked"], "2026-10-10")
        self.assertEqual(db["updated"], "2026-10-10")

    def test_records_are_slimmed(self):
        db = store.empty()
        store.update(db, lambda *_: [{"numeroConvocatoria": "1"}], fake_detail, date(2026, 10, 9), 45, log=quiet)
        record = db["calls"]["1"]
        self.assertNotIn("ignored_field", record)
        self.assertEqual(record["documentos"], [{"id": 7, "nombre": "bases.pdf"}])
        self.assertEqual(record["anuncios"][0]["fecha"], "2026-10-02")

    def test_a_failing_record_does_not_stop_the_run(self):
        def flaky(code):
            if code == "bad":
                raise OSError("timeout")
            return fake_detail(code)
        db = store.empty()
        found = lambda *_: [{"numeroConvocatoria": "bad"}, {"numeroConvocatoria": "ok"}]
        self.assertEqual(store.update(db, found, flaky, date(2026, 10, 9), 45, log=quiet), ["ok"])

    def test_long_closed_calls_are_forgotten(self):
        db = store.empty()
        store.update(db, lambda *_: [{"numeroConvocatoria": "1"}], fake_detail, date(2026, 10, 9), 45, log=quiet)
        store.forget_old(db, date(2027, 2, 28))  # closed on 31 Dec, 59 days earlier
        self.assertIn("1", db["calls"])
        store.forget_old(db, date(2027, 3, 2))
        self.assertNotIn("1", db["calls"])


if __name__ == "__main__":
    unittest.main()
