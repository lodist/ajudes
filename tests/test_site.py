import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from ayudas import site

TODAY = date(2026, 10, 9)


def record(code, level, second, title, **fields):
    data = {"codigo": code, "titulo": title, "organo": {"nivel1": level, "nivel2": second, "nivel3": None},
            "fechaRecepcion": "2026-09-18", "tipo": "Concurrencia competitiva - canónica", "regiones": ["ES523"],
            "beneficiarios": [1], "sectores": [], "first_seen": "2026-10-09", "notified": False}
    data.update(fields)
    return data


def sample_db():
    calls = [
        record("930260", "LOCAL", "MASSANASSA", "Convocatoria de ayudas para el fomento de la natalidad, tarjeta bebe 2027",
               textFin="Hasta el 30 de septiembre del 2027", presupuesto=30000, sede="https://sede.massanassa.es",
               documento={"id": 1523697, "nombre": "DECRETO 2026-1972.pdf"}, quien="Progenitores empadronados"),
        record("999001", "LOCAL", "POBLA DE VALLBONA, LA", "Premio <script>alert(1)</script> de relatos",
               fechaFinSolicitud="2026-11-15"),
        record("999002", "LOCAL", "VALENCIA", "SUBVENCIÓN NOMINATIVA LO RAT PENAT 2026"),
        record("999003", "LOCAL", "MASSANASSA", "Ayudas al comercio 2025", fechaFinSolicitud="2026-01-31"),
        record("999004", "LOCAL", "VALENCIA", "Ayuda a una entidad", tipo="Concesión directa - instrumental"),
        record("999005", "ESTADO", "MINISTERIO DE INDUSTRIA", "Ayudas para la digitalización de pymes",
               regiones=[], beneficiarios=[3], sectores=["G", "I"], fechaFinSolicitud="2026-12-01"),
        record("999006", "AUTONOMICA", "COMUNIDAD VALENCIANA", "Bono alquiler joven", regiones=["ES52"],
               fechaFinSolicitud="2026-10-30"),
        record("999007", "LOCAL", "MASSANASSA", "Ayudas a la natalidad 2026", regiones=["ES52"],
               fechaFinSolicitud="2026-12-31"),
        record("999008", "LOCAL", "CABRA", "Ayudas al estudio", regiones=["ES"], fechaFinSolicitud="2026-12-01"),
        record("999009", "ESTADO", "MINISTERIO DE EDUCACIÓN", "Subvenciones para acciones formativas", regiones=["ES"],
               beneficiarios=[1, 2, 3, 4], quien="Entidades de formación y agrupaciones de entidades",
               fechaFinSolicitud="2026-11-30"),
    ]
    return {"estado": {}, "calls": {c["codigo"]: c for c in calls}}


class Items(unittest.TestCase):
    def setUp(self):
        self.items = {i.code: i for i in site.items_from(sample_db(), TODAY)}

    def test_only_public_calls(self):
        self.assertNotIn("999002", self.items)
        self.assertNotIn("999004", self.items)

    def test_town_hall_announcement(self):
        baby = self.items["930260"]
        self.assertEqual((baby.place.town, baby.place.province), ("Massanassa", "ES523"))
        self.assertEqual(baby.title, "Ayudas para el fomento de la natalidad, tarjeta bebe 2027")
        self.assertEqual((baby.status, baby.topics[0]), ("abierta", "bebes"))
        self.assertEqual(self.items["999003"].status, "cerrada")

    def test_aid_for_organisations(self):
        """Open to "everyone" in the BDNS, but the paragraph on who can apply starts with organisations."""
        self.assertTrue(self.items["999009"].for_organisations)
        self.assertFalse(self.items["930260"].for_organisations)

    def test_town_province_learnt_from_its_other_announcements(self):
        self.assertEqual(self.items["999007"].place.province, "ES523")

    def test_data_files(self):
        self.assertEqual(site.files_for(self.items["930260"]), ["ES52"])
        self.assertEqual(site.files_for(self.items["999005"]), ["ES"])
        self.assertEqual(site.files_for(self.items["999006"]), ["ES52"])
        # A town hall we can't place isn't shown all over Spain.
        self.assertEqual((site.files_for(self.items["999008"]), self.items["999008"].listed), ([], False))

    def test_compact_json(self):
        data = site.item_json(self.items["999005"])
        self.assertEqual((data["k"], data["sc"], data["b"], data["sec"], data["e"], data["x"]),
                         ("e", ["ES"], [3], ["G", "I"], "2026-12-01", "x"))
        self.assertNotIn("w", data)

    def test_deadline_wording(self):
        self.assertEqual(site.deadline_text(self.items["999001"], TODAY),
                         ("Abierta", "hasta el 15 de noviembre (quedan 37 días)"))
        self.assertEqual(site.badge(self.items["999006"], TODAY), ("open", "oct", "30", "21 días"))


class Build(unittest.TestCase):
    def test_site_pages_data_feeds_and_sitemap(self):
        items = site.items_from(sample_db(), TODAY)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public"
            counts = site.build(items, out, TODAY, site_url="https://example.org/ayudas")
            self.assertEqual(counts["open"], 6)
            index = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("ayudas abiertas hoy", index)
            town = (out / "municipio" / "valencia" / "massanassa" / "index.html").read_text(encoding="utf-8")
            self.assertIn("tarjeta bebe 2027", town)
            self.assertIn('href="../../../style.css"', town)
            pobla = (out / "municipio" / "valencia" / "la-pobla-de-vallbona" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert", pobla)
            self.assertIn("&lt;script&gt;", pobla)
            self.assertTrue((out / "comunidad" / "comunitat-valenciana" / "index.html").exists())
            self.assertTrue((out / "provincia" / "valencia" / "index.html").exists())
            self.assertTrue((out / "tema" / "bebes" / "index.html").exists())
            self.assertTrue((out / "buscar.html").exists())
            meta = json.loads((out / "data" / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["towns"]["ES523"][0][:2], ["la-pobla-de-vallbona", "La Pobla de Vallbona"])
            spain = json.loads((out / "data" / "r" / "ES.json").read_text(encoding="utf-8"))
            valencia = json.loads((out / "data" / "r" / "ES52.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(i["c"] for i in spain), ["999005", "999009"])
            self.assertEqual(sorted(i["c"] for i in valencia), ["930260", "999001", "999006", "999007"])
            for feed in ("feed.xml", "comunidad/comunitat-valenciana/feed.xml", "sitemap.xml"):
                ET.parse(out / feed)
            sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("https://example.org/ayudas/municipio/valencia/massanassa/", sitemap)


if __name__ == "__main__":
    unittest.main()
