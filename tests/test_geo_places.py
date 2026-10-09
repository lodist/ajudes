import unittest

from ayudas import geo
from ayudas.places import place_of


def call(level, second, third=None, regions=(), bulletin=None):
    return {"organo": {"nivel1": level, "nivel2": second, "nivel3": third}, "regiones": list(regions),
            "boletin": {"diario": bulletin} if bulletin else None}


class Geo(unittest.TestCase):
    def test_codes_from_bdns_regions(self):
        self.assertEqual(geo.codes_from([{"descripcion": "ES523 - Valencia / València"}, {"descripcion": "XXXX - TODO EL MUNDO"}]),
                         ["ES523", "ES"])
        self.assertEqual(geo.codes_from(["ES61"]), ["ES61"])

    def test_names_in_organs(self):
        self.assertEqual(geo.province_in_text("DIPUTACIÓN PROV. DE VALENCIA"), "ES523")
        self.assertEqual(geo.province_in_text("DIPUTACIÓN FORAL DE BIZKAIA"), "ES213")
        self.assertEqual(geo.province_in_text("CABILDO INSULAR DE TENERIFE"), "ES709")
        self.assertEqual(geo.region_in_text("COMUNIDAD VALENCIANA"), "ES52")
        self.assertEqual(geo.region_in_text("CASTILLA LA MANCHA"), "ES42")
        self.assertEqual(geo.region_in_text("ANDALUCIA"), "ES61")

    def test_bulletins(self):
        self.assertEqual(geo.bulletin_area("B.O.P. DE ZARAGOZA"), "ES243")
        self.assertEqual(geo.bulletin_area("B.P. DEL TERRITORIO HISTÓRICO DE ÁLAVA"), "ES211")
        self.assertEqual(geo.bulletin_area("DOCV. D.O. DE LA COMUNITAT VALENCIANA"), "ES52")
        self.assertEqual(geo.bulletin_area("DOGC. D.O. DE LA GENERALITAT DE CATALUNYA"), "ES51")
        self.assertEqual(geo.bulletin_area("BORM. B.O. DE LA REGIÓN DE MURCIA"), "ES620")
        self.assertEqual(geo.bulletin_area("BON. B.O. DE NAVARRA"), "ES220")
        self.assertEqual(geo.bulletin_area("B.O.P. DE LAS PALMAS"), "ES70")  # several islands
        self.assertIsNone(geo.bulletin_area("BOE. BOLETÍN OFICIAL DEL ESTADO"))
        self.assertIsNone(geo.bulletin_area(None))

    def test_towns_named_like_their_province(self):
        self.assertEqual(geo.province_named("Zaragoza"), "ES243")
        self.assertEqual(geo.province_named("Alicante/Alacant"), "ES521")
        self.assertIsNone(geo.province_named("Valencia de Don Juan"))

    def test_slugs(self):
        self.assertEqual(geo.region_slug("ES52"), "comunitat-valenciana")
        self.assertEqual(geo.province_slug("ES523"), "valencia")
        self.assertEqual(geo.province_slug("ES211"), "araba")


class Places(unittest.TestCase):
    def test_town_hall(self):
        place = place_of(call("LOCAL", "POBLA DE VALLBONA, LA", "AYUNTAMIENTO DE LA POBLA", ["ES523 - Valencia"]))
        self.assertEqual((place.kind, place.town, place.town_slug, place.province, place.region),
                         ("municipio", "La Pobla de Vallbona", "la-pobla-de-vallbona", "ES523", "ES52"))
        self.assertEqual(place.organ, "Ayuntamiento de La Pobla de Vallbona")

    def test_provincial_body(self):
        place = place_of(call("LOCAL", "DIPUTACIÓN PROV. DE VALENCIA", "DIPUTACIÓN PROVINCIAL DE VALENCIA"))
        self.assertEqual((place.kind, place.organ, place.province, place.scope),
                         ("provincia", "Diputación de Valencia", "ES523", ("ES523",)))

    def test_regional_government(self):
        place = place_of(call("AUTONOMICA", "ANDALUCIA", "CONSEJERÍA DE EMPLEO", ["ES61 - ANDALUCIA"]))
        self.assertEqual((place.kind, place.organ, place.region), ("comunidad", "Junta de Andalucía", "ES61"))
        self.assertEqual(place_of(call("AUTONOMICA", "COMUNIDAD VALENCIANA")).region, "ES52")

    def test_bodies_only_fund_within_their_territory(self):
        """Some records say 'ES' (all of Spain) for a provincial or regional grant."""
        alicante = place_of(call("LOCAL", "DIPUTACIÓN PROV. DE ALICANTE", "DIPUTACIÓN PROVINCIAL DE ALACANT", ["ES"]))
        self.assertEqual((alicante.scope, alicante.province), (("ES521",), "ES521"))
        andalucia = place_of(call("AUTONOMICA", "ANDALUCÍA", "CONSEJERÍA DE EDUCACIÓN", ["ES"]))
        self.assertEqual((andalucia.scope, andalucia.region), (("ES61",), "ES61"))
        salamanca = place_of(call("OTROS", "UNIVERSIDAD DE SALAMANCA", None, ["ES"]))
        self.assertEqual((salamanca.scope, salamanca.region), (("ES415",), "ES41"))

    def test_town_halls_are_never_national(self):
        """Some town halls file their grants as 'ES': the bulletin or the town's name says where they are."""
        zaragoza = place_of(call("LOCAL", "ZARAGOZA", None, ["ES"], "B.O.P. DE ZARAGOZA"))
        self.assertEqual((zaragoza.scope, zaragoza.province, zaragoza.region), (("ES243",), "ES243", "ES24"))
        xativa = place_of(call("LOCAL", "XÀTIVA", None, ["ES52 - COMUNIDAD VALENCIANA"], "B.O.P. DE VALENCIA"))
        self.assertEqual((xativa.scope, xativa.province), (("ES523",), "ES523"))
        murcia = place_of(call("LOCAL", "MURCIA", None, ["ES"]))
        self.assertEqual((murcia.scope, murcia.province), (("ES620",), "ES620"))
        cabra = place_of(call("LOCAL", "CABRA", None, ["ES"]))
        self.assertEqual((cabra.kind, cabra.scope, cabra.region), ("municipio", (), None))
        parla = place_of(call("LOCAL", "PARLA", None, ["ES30 - COMUNIDAD DE MADRID"]))
        self.assertEqual((parla.scope, parla.province), (("ES300",), "ES300"))  # Madrid has one province
        regional = place_of(call("LOCAL", "BIAR", None, ["ES"], "DOCV. D.O. DE LA COMUNITAT VALENCIANA"))
        self.assertEqual((regional.scope, regional.region, regional.province), (("ES52",), "ES52", None))

    def test_supra_municipal_bodies(self):
        place = place_of(call("LOCAL", "MANCOMUNIDAD INTERMUNICIPAL BARRIO DEL CRISTO ALDAIA-QUART DE POBLET", None,
                              ["ES523 - Valencia"]))
        self.assertEqual((place.kind, place.scope, place.town), ("comarca", ("ES523",), None))

    def test_state_is_all_of_spain(self):
        place = place_of(call("ESTADO", "MINISTERIO DE CULTURA"))
        self.assertEqual((place.kind, place.scope), ("estado", ("ES",)))

    def test_university(self):
        place = place_of(call("OTROS", "UNIVERSITAT DE VALÈNCIA (ESTUDI GENERAL)", None, ["ES523 - Valencia"]))
        self.assertEqual((place.kind, place.organ, place.region), ("otros", "Universitat de València (Estudi General)", "ES52"))


if __name__ == "__main__":
    unittest.main()
