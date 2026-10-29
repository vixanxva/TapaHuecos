from datetime import datetime, timedelta, timezone

import gpxpy.gpx
import pytest


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
