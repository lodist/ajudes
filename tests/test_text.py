import unittest

from ayudas.text import clean_title, looks_abbreviated, nice_place, normalize, slugify


class PlaceNames(unittest.TestCase):
    def test_article_moves_to_the_front(self):
        self.assertEqual(nice_place("POBLA DE VALLBONA, LA"), "La Pobla de Vallbona")
        self.assertEqual(nice_place("ELIANA, L'"), "L'Eliana")
        self.assertEqual(nice_place("MONTESINOS, LOS"), "Los Montesinos")

    def test_bilingual_names_keep_both_forms(self):
        self.assertEqual(nice_place("ALCOY/ALCOI"), "Alcoy/Alcoi")
        self.assertEqual(nice_place("FONDÓ DE LES NEUS, EL/HONDÓN DE LAS NIEVES"),
                         "El Fondó de les Neus/Hondón de las Nieves")
        self.assertEqual(nice_place("SAN VICENTE DEL RASPEIG/SANT VICENT DEL RASPEIG"),
                         "San Vicente del Raspeig/Sant Vicent del Raspeig")

    def test_minor_local_entity_suffix_is_dropped(self):
        self.assertEqual(nice_place("PERELLÓ, EL, ENTIDAD LOCAL MENOR"), "El Perelló")
        self.assertEqual(nice_place("JESÚS POBRE, ENTIDAD LOCAL MENOR "), "Jesús Pobre")

    def test_words_in_brackets_are_capitalised(self):
        self.assertEqual(nice_place("UNIVERSITAT DE VALÈNCIA (ESTUDI GENERAL)"),
                         "Universitat de València (Estudi General)")


class Titles(unittest.TestCase):
    def test_resolution_preamble_and_procedure_jargon_are_removed(self):
        self.assertEqual(
            clean_title("Extracto de la Resolución de la Alcaldía núm 2026-3793 de fecha 7 de octubre de 2026, por "
                        "la que se convoca la concesión de subvenciones en régimen de concurrencia competitiva a "
                        "entidades y asociaciones municipales de carácter social, ejercicio 2026"),
            "Subvenciones a entidades y asociaciones municipales de carácter social, ejercicio 2026")

    def test_all_caps_titles_are_calmed_down(self):
        self.assertEqual(clean_title("BASES SUBVENCIÓN PARA LA COMPRA O AUTOPROMOCIÓN DE PRIMERA VIVIENDA, "
                                     "EJERCICIO 2026"),
                         "Subvención para la compra o autopromoción de primera vivienda, ejercicio 2026")

    def test_file_number_and_approval_prefixes(self):
        self.assertEqual(clean_title("Expediente 3027535K: APROBACIÓN BASES Y CONVOCATORIA AYUDAS ECONÓMICAS PARA "
                                     "FAMILIAS MONOPARENTALES EJERCICIO 2026 "),
                         "Ayudas económicas para familias monoparentales ejercicio 2026")

    def test_place_names_acronyms_and_roman_numerals_survive(self):
        self.assertEqual(clean_title("BASES REGULADORAS DE LA IV CAMPAÑA BONOS COMERCIO DEL PERELLÓ TRAS LA DANA",
                                     names=("El Perelló",)),
                         "IV campaña bonos comercio del Perelló tras la DANA")

    def test_only_the_shouting_part_is_lower_cased(self):
        self.assertEqual(clean_title("CHEQUE BEBÉ - Concesión de ayudas económicas para gastos directamente "
                                     "derivados del nacimiento."),
                         "Cheque bebé - Concesión de ayudas económicas para gastos directamente derivados del "
                         "nacimiento")

    def test_announcement_preamble(self):
        self.assertEqual(clean_title("Anuncio del Ayuntamiento de Benetússer sobre la convocatoria para la concesión "
                                     "de ayudas para personas con discapacidad"),
                         "Ayudas para personas con discapacidad")

    def test_other_preambles_and_decree_references(self):
        self.assertEqual(clean_title("Resolución de la Alcaldía nº 3820 de 2 de septiembre - Convocatoria anual de "
                                     "ayudas económicas a jóvenes"),
                         "Ayudas económicas a jóvenes")
        self.assertEqual(clean_title("Ayuntamiento de Massalfassar para la concesión de ayudas en materia de cheque "
                                     "escolar - curso 2026-2027"),
                         "Ayudas en materia de cheque escolar - curso 2026-2027")
        self.assertEqual(clean_title("Ayudas en materia educativa curso 2026-2027 (Decreto nº 305 de 09/07/2026)"),
                         "Ayudas en materia educativa curso 2026-2027")

    def test_dated_headers_and_abbreviated_jargon(self):
        self.assertEqual(clean_title("Convocatoria de 16 de septiembre de 2026, del Vicerrectorado de Internacionalización "
                                     "de la Universidad de Salamanca, de ayudas a la movilidad de estudiantes"),
                         "Ayudas a la movilidad de estudiantes")
        self.assertEqual(clean_title("Resolución de 25 de septiembre de 2026, de la Dirección General, por la que se "
                                     "convocan ayudas por desplazamiento, en rég. de conc. comp., al alumnado"),
                         "Ayudas por desplazamiento al alumnado")
        self.assertEqual(clean_title("Decreto nº 2026-4159, por el que se aprueba convocatoria pública anticipada de dos "
                                     "Becas de Formación"),
                         "Dos Becas de Formación")

    def test_years_quotes_and_published_bases(self):
        self.assertEqual(clean_title("Convocatoria 2026 de ayudas Campaña de Reyes"), "Ayudas Campaña de Reyes")
        self.assertEqual(clean_title("`CONVOCATORIA PÚBLICA PARA LA CONCESIÓN DE SUBVENCIONES PARA PROYECTOS DE TEATRO`"),
                         "Subvenciones para proyectos de teatro")
        self.assertEqual(clean_title("Resolución de la Universidad por la que se convocan y hacen públicas las bases "
                                     "reguladoras de la convocatoria 2026 para la concesión de ayudas de movilidad"),
                         "Ayudas de movilidad")
        self.assertEqual(clean_title("EXTRACTO de la Orden 3190/2026, de la Consejería de Medio Ambiente, por la que se "
                                     "procede a la apertura y convocatoria de participación en el Programa Agroambiental"),
                         "Programa Agroambiental")

    def test_more_ways_of_saying_convocatoria(self):
        cases = {
            "2026 CONVOCATORIA Ayudas para el Fomento del Tejido Comercial": "Ayudas para el Fomento del Tejido Comercial",
            "Resolución convocatoria para la concesión de ayudas económicas para opositores":
                "Ayudas económicas para opositores",
            "RESOLUCIÓN del dir gral de Cultura, de convocatoria de subvenciones a las artes escénicas":
                "Subvenciones a las artes escénicas",
            "Resolución de la Viceconsejería, por la que se realiza la convocatoria para el año 2026 de las ayudas "
            "para el mantenimiento de la raza": "Ayudas para el mantenimiento de la raza",
            "Extracto de la Resolución de 30/09/2026, del Director del Instituto de Fomento, por delegación, de "
            "convocatoria de ayudas a ferias": "Ayudas a ferias",
            "Acuerdo Junta de Gobierno Local de 26 de agosto de 2026 que aprueba la convocatoria para la concesión "
            "de becas juveniles": "Becas juveniles",
            "Acuerdo del Consejo Ejecutivo, de 31 de agosto de 2026, relativo a la convocatoria de ayudas para "
            "personas con discapacidad": "Ayudas para personas con discapacidad",
            "Bases que deben regir la convocatoria pública de subvenciones para fachadas": "Subvenciones para fachadas",
            "Decreto de Alcaldía por el que se aprueban las bases y concesión de subvenciones por procedimiento de "
            "concurrencia competitiva de ayudas al estudio": "Subvenciones de ayudas al estudio",
            "Concesion ayudas municipales para libros de texto": "Ayudas municipales para libros de texto",
            "Anuncio convocatoria concesión de ayudas para la primera infancia": "Ayudas para la primera infancia",
            "Decreto de Alcaldía 26/68 convocatoria de ayudas a la conciliación familiar":
                "Ayudas a la conciliación familiar",
            "Las ayudas para el transporte en taxi \"Bonotaxi 2027": "Ayudas para el transporte en taxi Bonotaxi 2027",
            "Convocatorias 2026: ayudas al transporte para mayores de 60 años": "Ayudas al transporte para mayores de 60 años",
            "Orden de la consejería de turismo por la que se autoriza el gasto y se aprueba la convocatoria de ayudas "
            "a deportistas": "Ayudas a deportistas",
            "CONVOCATORIA PARA LA CONCESIÓN, EN RÉGIMEN DE CONCURRENCIA COMPETITIVA, DE SUBVENCIONES A DEPORTISTAS":
                "Subvenciones a deportistas",
            "DECRETO DE ALCALDÍA NÚM. 386/2026, DEL 22/09/2026, POR EL QUE SE APRUEBAN LAS BASES Y SE CONVOCAN LAS "
            "AYUDAS PARA TRANSPORTE ESCOLAR": "Ayudas para transporte escolar",
            "BASES Y CONVOCATORIA QUE REGULAN LA CONCESIÓN DE AYUDAS A JÓVENES": "Ayudas a jóvenes",
            "CONVOCATORIA 2026 QUE REGULA LA SOLICITUD Y CONCESIÓN DE AYUDAS PARA APRENDER EUSKERA":
                "Ayudas para aprender euskera",
            "Resolución de 29/07/2026 de la Agencia de Ciencia que aprueba convocatoria de ayudas a inversiones":
                "Ayudas a inversiones",
            "Resolución de la consejera de Inclusión Social, Juventud, Familias e Igualdad de convocatoria de "
            "subvenciones a particulares": "Subvenciones a particulares",
            "Acuerdo de aprobación de la Junta de Gobierno Local de las bases de la convocatoria de ayudas a familias":
                "Ayudas a familias",
            "Por resolución de la alcaldía de 16 de septiembre de 2026 por la que se aprueban las bases y la "
            "convocatoria de bonos de otoño": "Bonos de otoño",
            "Convocatoria ejercicio 2026 para la concesión de ayudas a la natalidad": "Ayudas a la natalidad",
            "Resolución de 21 de julio de 2026 de ICEX, por la que se convocan para 2026 la concesión de subvenciones "
            "del Programa ICEX Next": "Subvenciones del Programa ICEX Next",
            "Resolución de la Secretaría de Estado de Industria por la que se aprueba la convocatoria correspondiente "
            "al año 2026 de la Línea 1 del Programa Auto+": "Línea 1 del Programa Auto+",
            "Extracte convocatòria de subvencions de l¿ajuntament de Vacarisses": "Subvencions de l'ajuntament de Vacarisses",
            "Las BBRR para la concesión de subvenciones para eficiencia energética":
                "Subvenciones para eficiencia energética",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(clean_title(raw), expected)

    def test_abbreviated_titles_are_spotted(self):
        self.assertTrue(looks_abbreviated("FEADER.AYUD.MANT.VIÑEDO SECANO PRESERVA BIODIVERSIDAD"))
        self.assertFalse(looks_abbreviated("Ayudas a los usuarios del aula matinal de los C.E.I.P."))

    def test_short_results_fall_back_to_the_original(self):
        self.assertEqual(clean_title("Convocatoria de becas"), "Convocatoria de becas")

    def test_long_titles_are_cut_on_a_word(self):
        title = clean_title("Ayudas " + "para familias " * 30)
        self.assertLessEqual(len(title), 171)
        self.assertTrue(title.endswith("…"))


class Helpers(unittest.TestCase):
    def test_normalize_and_slugify(self):
        self.assertEqual(normalize("  Xàbia’S  Bebé "), "xabia's bebe")
        self.assertEqual(slugify("La Pobla de Vallbona"), "la-pobla-de-vallbona")
        self.assertEqual(slugify("Alcoy/Alcoi"), "alcoy-alcoi")


if __name__ == "__main__":
    unittest.main()
