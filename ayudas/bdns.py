"""Small client for the public API of Spain's national grants database (BDNS).

API docs: https://www.infosubvenciones.es/bdnstrans/doc/swagger
Reuse terms: https://www.infosubvenciones.es/bdnstrans/GE/es/avisolegal
"""
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.infosubvenciones.es/bdnstrans/api"
WEB = "https://www.infosubvenciones.es/bdnstrans/GE/es"
USER_AGENT = "ajudes/0.1"
COMUNITAT_VALENCIANA = "54,55,56,57"  # region ids: the Comunitat plus Alicante, Castellón and Valencia
INDIVIDUALS = "1"  # "personas físicas que no desarrollan actividad económica"
PAUSE_SECONDS = 0.4  # the API is a free public service: one request at a time, gently


def _get(path: str, **params) -> dict:
    url = f"{API}/{path}?{urllib.parse.urlencode(params, safe='/,')}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def search(since: dt.date, until: dt.date, regions: str = COMUNITAT_VALENCIANA,
           beneficiaries: str = INDIVIDUALS) -> list[dict]:
    """Summaries of the announcements registered between two dates."""
    calls, page = [], 0
    while True:
        data = _get("convocatorias/busqueda", vpd="GE", page=page, pageSize=100, regiones=regions,
                    tiposBeneficiario=beneficiaries, fechaDesde=f"{since:%d/%m/%Y}", fechaHasta=f"{until:%d/%m/%Y}")
        calls.extend(data["content"])
        if data.get("last", True):
            return calls
        page += 1
        time.sleep(PAUSE_SECONDS)


def detail(code: str) -> dict:
    """Full record of one announcement, by its BDNS code."""
    time.sleep(PAUSE_SECONDS)
    data = _get("convocatorias", numConv=code, vpd="GE")
    data.pop("advertencia", None)
    return data


def call_url(code: str) -> str:
    return f"{WEB}/convocatoria/{code}"


def document_url(document_id: int | str) -> str:
    return f"{API}/convocatorias/documentos?idDocumento={document_id}"
