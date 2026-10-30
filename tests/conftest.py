import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gpxpy.gpx
import pytest

_RUTA_GENERADOR = Path(__file__).parent / "fixtures" / "generar.py"
_spec = importlib.util.spec_from_file_location("generar_fixtures", _RUTA_GENERADOR)
generar_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_fixtures)


@pytest.fixture
def gpx_recto(tmp_path):
    """GPX de 60 s avanzando hacia el norte desde Montería, un punto por segundo."""
    inicio = datetime(2026, 10, 29, 19, 30, 0, tzinfo=timezone.utc)  # 14:30 en Colombia
    gpx = gpxpy.gpx.GPX()
    pista = gpxpy.gpx.GPXTrack()
    segmento = gpxpy.gpx.GPXTrackSegment()
    for s in range(61):
        segmento.points.append(
            gpxpy.gpx.GPXTrackPoint(8.75 + s * 0.0001, -75.88, time=inicio + timedelta(seconds=s))
        )
    pista.segments.append(segmento)
    gpx.tracks.append(pista)
    ruta = tmp_path / "recorrido.gpx"
    ruta.write_text(gpx.to_xml(), encoding="utf-8")
    return ruta, inicio


@pytest.fixture(scope="session")
def datos_prueba(tmp_path_factory):
    """Video, imagen, GPX y verdad de campo de tests/fixtures/generar.py, creados una vez por sesión."""
    return generar_fixtures.generar(tmp_path_factory.mktemp("fixtures"))
