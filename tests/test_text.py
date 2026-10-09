import unittest

from ayudas.text import clean_title, nice_place, normalize, slugify


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
