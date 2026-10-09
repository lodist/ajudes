import unittest

from ayudas.topics import classify

# Real titles from the BDNS, and the topic a person would look for them under.
CASES = {
    "Ayudas por nacimiento, adopción o acogida denominadas “Ben *Rebuda” para el año 2026": "bebes",
    "AYUDA MATERIAL ESCOLAR, CONVOCATORIA 2026-2027": "colegio",
    "CONVOCATORIA DE BECAS COMEDOR ESCOLAR DEL AYUNTAMIENTO DE ROCAFORT CURSO 2026-2027": "colegio",
    "Convocatoria bases ayudas al transporte de estudiantes ejercicio 2026-2027": "estudios",
    "BASES SUBVENCIÓN PARA LA COMPRA O AUTOPROMOCIÓN DE PRIMERA VIVIENDA, EJERCICIO 2026": "vivienda",
    "Ayudas destinadas al pago de cualquier suministro de la vivienda habitual (agua, electricidad y gas)": "facturas",
    "2ª convocatoria de ayudas a personas propietarias de vehículos a motor retirados de las campas municipales "
    "tras la DANA del 29 de octubre de 2024": "dana",
    "BASES CONVOCATORIA CAMPAÑA BONOS CONSUM MONÒVER CAMPAÑA 2026": "bonos",
    "Subvenciones deportistas de élite y promesas de Burriana": "deporte",
    "PREMIOS ARTES Y CREATIVIDAD JOVEN 2026": "premios",
    "Bases reguladoras y convocatoria de la II Edición del concurso de fotografía contra la violencia de género":
        "premios",
    "Expediente 2844090A: APROBACIÓN BASES Y CONVOCATORIA AYUDAS ECONÓMICAS PARA PERSONAS CON CELIAQUÍA": "salud",
    "Convocatoria de ayudas para la participación de personas con discapacidad escolarizadas en centros de "
    "educación especial": "salud",
    "APROBACIÓN BASES Y CONVOCATORIA AYUDAS ECONÓMICAS PARA FAMILIAS MONOPARENTALES EJERCICIO 2026": "social",
    "Acuerdo por el que se aprueba la convocatoria pública del programa Aspe Emprende, anualidad 2026": "empleo",
    "Concurso general de becas y ayudas a los gastos de estudio para el curso académico 2026–2027": "estudios",
    "Subvención para cubrir el coste de la tasa de las certificaciones en los idiomas valenciano, inglés": "estudios",
    "Ayudas en materia educativa curso 2026-2027": "colegio",
    "Subvenciones destinadas al bono comercial 2026": "bonos",
    "Ayudas para sufragar parte de los gastos de haber obtenido el permiso de conducir": "transporte",
    "Convocatoria anual de ayudas económicas a jóvenes": "jovenes",
    "Subvención jóvenes deportistas": "deporte",
}


class Topics(unittest.TestCase):
    def test_main_topic_of_real_titles(self):
        for title, expected in CASES.items():
            with self.subTest(title=title):
                self.assertEqual(classify(title)[0], expected)

    def test_valencian_titles(self):
        self.assertEqual(classify("Ajudes per naixement, adopció o acolliment")[0], "bebes")
        self.assertEqual(classify("Bons consum per al comerç local de Xàbia")[0], "bonos")

    def test_unknown_titles_go_to_other(self):
        self.assertEqual(classify("Algo completamente distinto"), ["otras"])

    def test_several_topics_can_match(self):
        self.assertEqual(classify("Ayudas al transporte de estudiantes")[:2], ["estudios", "transporte"])

    def test_main_topic_comes_from_the_title_not_the_bulletin(self):
        found = classify("Ayudas para personas en situación de vulnerabilidad, AYUDAS DANA",
                         "Ayudas para personas escolarizadas en centros educativos específicos")
        self.assertEqual(found[0], "dana")
        self.assertIn("social", found)


if __name__ == "__main__":
    unittest.main()
