from datetime import datetime, timezone
from pathlib import Path

from tapahuecos.entrada import inicio_desde_nombre, interpretar_fecha, resolver_inicio


def test_fecha_desde_nombre_android():
    inicio = inicio_desde_nombre("VID_20261029_143015.mp4", -5)
    assert inicio.astimezone(timezone.utc) == datetime(2026, 10, 29, 19, 30, 15, tzinfo=timezone.utc)


def test_nombre_sin_fecha():
    assert inicio_desde_nombre("IMG_1234.MOV", -5) is None


def test_fecha_iso_con_y_sin_zona():
    assert interpretar_fecha("2026-10-29T14:30:15", -5).utcoffset().total_seconds() == -5 * 3600
    assert interpretar_fecha("2026-10-29T19:30:15Z", -5).utcoffset().total_seconds() == 0


def test_configuracion_tiene_prioridad():
    inicio = resolver_inicio(Path("VID_20261029_143015.mp4"), "2026-01-01T00:00:00", -5)
    assert inicio.year == 2026 and inicio.month == 1
