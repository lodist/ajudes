import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from ayudas import site

TODAY = date(2026, 10, 9)


def record(code, town, title, **fields):
    data = {"codigoBDNS": code, "organo": {"nivel1": "LOCAL", "nivel2": town, "nivel3": f"AYUNTAMIENTO DE {town}"},
            "descripcion": title, "fechaRecepcion": "2026-09-18", "tipoConvocatoria": "Concurrencia competitiva",
            "regiones": [{"descripcion": "ES523 - Valencia / València"}], "documentos": [], "anuncios": [],
            "first_seen": "2026-10-09", "notified": False}
    data.update(fields)
    return data


def sample_db():
    return {"updated": "2026-10-09", "calls": {
        "930260": record("930260", "MASSANASSA", "Convocatoria de ayudas para el fomento de la natalidad, tarjeta "
                         "bebe 2027", textFin="Hasta el 30 de septiembre del 2027", presupuestoTotal=30000,
                         documentos=[{"id": 1523697, "nombre": "DECRETO 2026-1972.pdf"}],
                         sedeElectronica="https//sede.massanassa.es",
                         anuncios=[{"titulo": "Extracto", "fecha": "2026-09-20", "url": "https://bop.example/1",
                                    "texto": "<p>Primero. Personas beneficiarias</p><p>Progenitores empadronados en "
                                             "Massanassa con hijos nacidos o adoptados.</p><p>Segundo. Finalidad</p>"}]),
        "999001": record("999001", "POBLA DE VALLBONA, LA", "Premio <script>alert(1)</script> de relatos",
                         fechaFinSolicitud="2026-11-15"),
        "999002": record("999002", "VALENCIA", "SUBVENCIÓN NOMINATIVA LO RAT PENAT 2026"),
        "999003": record("999003", "MASSANASSA", "Ayudas al comercio 2025", fechaFinSolicitud="2026-01-31"),
        "999004": record("999004", "VALENCIA", "Ayuda a una entidad", tipoConvocatoria="Concesión directa - instrumental"),
    }}


class Items(unittest.TestCase):
    def test_announcements_become_readable_items(self):
        items = {i.code: i for i in site.items_from(sample_db(), TODAY)}
        self.assertNotIn("999002", items)  # grants named for one association are not for the public
        self.assertNotIn("999004", items)
        baby = items["930260"]
        self.assertEqual(baby.place.name, "Massanassa")
        self.assertEqual(baby.title, "Ayudas para el fomento de la natalidad, tarjeta bebe 2027")
        self.assertEqual(baby.status, "abierta")
        self.assertEqual(baby.topics[0], "bebes")
        self.assertEqual(baby.who, "Progenitores empadronados en Massanassa con hijos nacidos o adoptados")
        self.assertEqual(baby.office_url, "https://sede.massanassa.es")
        self.assertEqual(items["999003"].status, "cerrada")

    def test_who_can_apply_comes_from_the_section_heading_only(self):
        inline = [{"texto": "<p>Tercero. Personas beneficiarias Podrán acogerse a las subvenciones las personas "
                            "físicas</p><p>Cuarto. Cuantía</p>"}]
        self.assertEqual(site._who(inline), "Podrán acogerse a las subvenciones las personas físicas")
        numbered = [{"texto": "<p>1.- Personas beneficiarias: padres o tutores de alumnos empadronados.</p>"
                              "<p>2.- Objeto: libros</p>"}]
        self.assertEqual(site._who(numbered), "padres o tutores de alumnos empadronados")
        passing = [{"texto": "<p>Objeto: ayudas para las familias beneficiarias del programa municipal</p>"}]
        self.assertIsNone(site._who(passing))

    def test_deadline_wording(self):
        items = {i.code: i for i in site.items_from(sample_db(), TODAY)}
        self.assertEqual(site.deadline_text(items["999001"], TODAY), ("Abierta", "hasta el 15 de noviembre (quedan 37 días)"))
        self.assertEqual(site.deadline_text(items["930260"], TODAY)[1],
                         "hasta el 30 de septiembre de 2027 (quedan 356 días)")


class Build(unittest.TestCase):
    def test_site_pages_feeds_and_sitemap(self):
        items = site.items_from(sample_db(), TODAY)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public"
            counts = site.build(items, out, TODAY, site_url="https://example.org/ayudas")
            index = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("tarjeta bebe 2027", index)
            self.assertNotIn("<script>alert", index)
            self.assertIn("&lt;script&gt;", index)
            self.assertNotIn("Rat Penat", index)
            self.assertNotIn("comercio 2025", index)  # closed: only shown on the town page
            town = (out / "municipio" / "massanassa" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Cerradas recientemente", town)
            self.assertTrue((out / "municipio" / "la-pobla-de-vallbona" / "index.html").exists())
            self.assertTrue((out / "tema" / "bebes" / "index.html").exists())
            for feed in ("feed.xml", "tema/bebes/feed.xml", "municipio/massanassa/feed.xml", "sitemap.xml"):
                ET.parse(out / feed)  # well-formed XML
            sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("https://example.org/ayudas/municipio/massanassa/", sitemap)
            self.assertEqual(counts["open"], 2)


if __name__ == "__main__":
    unittest.main()
