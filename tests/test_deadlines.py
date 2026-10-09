import unittest
from datetime import date

from ayudas.deadlines import Window, add_months, add_working_days, status, window


def call(**fields):
    record = {"fechaRecepcion": "2026-10-07"}  # a Wednesday
    record.update(fields)
    return record


class Windows(unittest.TestCase):
    def test_dates_given_by_the_database(self):
        win = window(call(fechaInicioSolicitud="2026-10-07", fechaFinSolicitud="2026-10-26"))
        self.assertEqual((win.start, win.end, win.precision), (date(2026, 10, 7), date(2026, 10, 26), "exact"))

    def test_dates_written_in_the_text(self):
        self.assertEqual(window(call(textFin="Hasta el 30 de septiembre del 2027")).end, date(2027, 9, 30))
        self.assertEqual(window(call(textFin="el dia 8 d’OCTUBRE DE 2026")).end, date(2026, 10, 8))
        self.assertEqual(window(call(textFin="31/12/2026")).end, date(2026, 12, 31))

    def test_working_days_from_the_bulletin_date(self):
        # Published Thursday 8 October: Fri 9, Mon 12 ... Thu 22 is the tenth working day.
        win = window(call(textFin="10 días hábiles desde el día siguiente a la publicación en el BOP",
                          anuncios=[{"fecha": "2026-10-08"}]))
        self.assertEqual((win.end, win.precision, win.period), (date(2026, 10, 22), "computed", "10 días hábiles"))
        self.assertEqual(win.start, date(2026, 10, 9))

    def test_days_without_a_bulletin_date_give_a_lower_bound(self):
        win = window(call(textFin="20 días naturales desde la publicación"))
        self.assertEqual((win.end, win.precision), (date(2026, 10, 27), "earliest"))
        self.assertIsNone(win.start)

    def test_days_default_to_working_days(self):
        self.assertEqual(window(call(textFin="Diez días a contar desde el día siguiente")).period, "10 días hábiles")

    def test_valencian_and_months(self):
        self.assertEqual(window(call(textFin="10 dies naturals.")).end, date(2026, 10, 17))
        self.assertEqual(window(call(textFin="Un mes.", anuncios=[{"fecha": "2026-01-31"}])).end, date(2026, 2, 28))

    def test_period_in_the_start_text(self):
        self.assertEqual(window(call(textInicio="20 días desde el día siguiente a la publicación")).period,
                         "20 días hábiles")

    def test_other_ways_of_writing_periods(self):
        self.assertEqual(window(call(textFin="Treinta (30) días naturales a partir del día siguiente")).end,
                         date(2026, 11, 6))
        self.assertEqual(window(call(textFin="Viente días naturales a partir del día siguiente")).period,
                         "20 días naturales")
        self.assertEqual(window(call(textFin="El 15º día hábil posterior a la publicación")).period, "15 días hábiles")
        self.assertEqual(window(call(textFin="PASADAS 8 SEMANAS DESDE EL DÍA SIGUIENTE")).end, date(2026, 12, 2))

    def test_short_years_and_dates_without_a_year(self):
        self.assertEqual(window(call(textFin="30/11/26")).end, date(2026, 11, 30))
        self.assertEqual(window(call(textFin="Hasta el dia 27 de juliol a les 14.00 h")).end, date(2027, 7, 27))
        self.assertEqual(window(call(textFin="31 de octubre")).end, date(2026, 10, 31))
        self.assertEqual(window(call(textFin="ÚLTIMO DÍA DEL AÑO EN QUE ESTÉ CONVOCADA")).end, date(2026, 12, 31))

    def test_dates_of_laws_are_not_deadlines(self):
        self.assertIsNone(window(call(textFin="Según la Ley 39/2015, de 1 de octubre")).end)

    def test_no_deadline(self):
        self.assertIsNone(window(call(textFin="curso escolar")).end)
        self.assertIsNone(window(call(textFin="No procede")).end)
        self.assertIsNone(window(call(textFin="18/0/2026")).end)


class Helpers(unittest.TestCase):
    def test_working_days_skip_weekends(self):
        self.assertEqual(add_working_days(date(2026, 10, 9), 1), date(2026, 10, 12))  # Friday -> Monday

    def test_months_keep_the_day_or_use_the_last_one(self):
        self.assertEqual(add_months(date(2026, 10, 7), 2), date(2026, 12, 7))
        self.assertEqual(add_months(date(2026, 12, 31), 2), date(2027, 2, 28))


class Status(unittest.TestCase):
    def test_exact_window(self):
        win = Window(date(2026, 10, 7), date(2026, 10, 26), "exact")
        self.assertEqual(status(win, date(2026, 10, 1)), "proxima")
        self.assertEqual(status(win, date(2026, 10, 26)), "abierta")
        self.assertEqual(status(win, date(2026, 10, 27)), "cerrada")

    def test_lower_bound_window_is_shown_as_may_have_closed_for_a_while(self):
        win = Window(None, date(2026, 10, 17), "earliest", "10 días naturales")
        self.assertEqual(status(win, date(2026, 10, 20)), "revisar")
        self.assertEqual(status(win, date(2026, 11, 30)), "cerrada")

    def test_unknown_end(self):
        self.assertEqual(status(Window(None, None, "exact"), date(2026, 10, 9)), "sin_fecha")


if __name__ == "__main__":
    unittest.main()
