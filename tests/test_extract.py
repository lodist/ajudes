import unittest

from ayudas import extract


class Extract(unittest.TestCase):
    def test_beneficiary_types(self):
        types = extract.beneficiary_types([
            {"descripcion": "PERSONAS FÍSICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA"},
            {"descripcion": "PYME Y PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA"},
            {"descripcion": "GRAN EMPRESA"}])
        self.assertEqual(types, [1, 3, 4])
        self.assertEqual(extract.beneficiary_types([{"descripcion": "PERSONAS JURÍDICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA"}]), [2])
        self.assertEqual(extract.beneficiary_types([]), [5])

    def test_sections_mix_letters_and_numbers(self):
        self.assertEqual(extract.sections(["G", "85.5", "01.1", "62", "Z"]), ["A", "G", "K", "Q"])

    def test_who_can_apply_comes_from_the_section_heading_only(self):
        inline = [{"texto": "<p>Tercero. Personas beneficiarias Podrán acogerse a las subvenciones las personas "
                            "físicas</p><p>Cuarto. Cuantía</p>"}]
        self.assertEqual(extract.who_can_apply(inline), "Podrán acogerse a las subvenciones las personas físicas")
        numbered = [{"texto": "<p>1.- Personas beneficiarias: padres o tutores de alumnos empadronados.</p>"
                              "<p>2.- Objeto: libros</p>"}]
        self.assertEqual(extract.who_can_apply(numbered), "padres o tutores de alumnos empadronados")
        passing = [{"texto": "<p>Objeto: ayudas para las familias beneficiarias del programa municipal</p>"}]
        self.assertIsNone(extract.who_can_apply(passing))

    def test_best_document_prefers_the_rules_in_spanish(self):
        documents = [{"id": 1, "nombreFic": "Model solicitud.pdf"}, {"id": 2, "nombreFic": "BASES - valencià.pdf"},
                     {"id": 3, "nombreFic": "BASES - castellà.pdf"}]
        self.assertEqual(extract.best_document(documents), {"id": 3, "nombre": "BASES - castellà.pdf"})
        self.assertIsNone(extract.best_document([]))

    def test_fix_url(self):
        self.assertEqual(extract.fix_url("https//sede.xirivella.es"), "https://sede.xirivella.es")
        self.assertEqual(extract.fix_url("https: sede.xixona.es"), "https://sede.xixona.es")
        self.assertEqual(extract.fix_url("www.vilademuro.net"), "https://www.vilademuro.net")
        self.assertIsNone(extract.fix_url("No procede"))


if __name__ == "__main__":
    unittest.main()
