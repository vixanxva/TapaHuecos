from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from tapahuecos.entrada import FuenteVideo, inicio_desde_nombre, interpretar_fecha, resolver_inicio


def _video_sintetico(ruta, fotogramas=12, fps=10, ancho=64, alto=48):
    """Fondo negro con un cuadro blanco de 8x8 en la esquina superior izquierda."""
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), fps, (ancho, alto))
    for _ in range(fotogramas):
        cuadro = np.zeros((alto, ancho, 3), np.uint8)
        cuadro[:8, :8] = 255
        escritor.write(cuadro)
    escritor.release()


class CapturaFalsa:
    """Imita cv2.VideoCapture devolviendo marcas de tiempo (ms) elegidas por la prueba."""

    def __init__(self, marcas_ms):
        self.marcas_ms = marcas_ms
        self.actual = -1

    def grab(self):
        self.actual += 1
        return self.actual < len(self.marcas_ms)

    def retrieve(self):
        return True, np.zeros((4, 4, 3), np.uint8)

    def get(self, propiedad):
        assert propiedad == cv2.CAP_PROP_POS_MSEC
        return self.marcas_ms[self.actual]

    def release(self):
        pass


def _fuente_falsa(tmp_path, marcas_ms, fps=25.0):
    ruta = tmp_path / "falso.avi"
    _video_sintetico(ruta, fotogramas=1)
    fuente = FuenteVideo(ruta)
    fuente.cerrar()
    fuente._cap = CapturaFalsa(marcas_ms)
    fuente.fps = fps
    return fuente


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("VID_20261029_143015.mp4", datetime(2026, 10, 29, 19, 30, 15, tzinfo=timezone.utc)),  # Android
        ("PXL_20261029_143015123.mp4", datetime(2026, 10, 29, 19, 30, 15, tzinfo=timezone.utc)),  # Pixel
        ("20261029_143015.mp4", datetime(2026, 10, 29, 19, 30, 15, tzinfo=timezone.utc)),  # Samsung
        ("VID-20261029-WA0001.mp4", None),  # WhatsApp: solo trae la fecha
        ("IMG_1234.MOV", None),
    ],
)
def test_fecha_desde_nombre(nombre, esperado):
    inicio = inicio_desde_nombre(nombre, -5)
    if esperado is None:
        assert inicio is None
    else:
        assert inicio.astimezone(timezone.utc) == esperado


def test_fecha_iso_con_y_sin_zona():
    assert interpretar_fecha("2026-10-29T14:30:15", -5).utcoffset().total_seconds() == -5 * 3600
    assert interpretar_fecha("2026-10-29T19:30:15Z", -5).utcoffset().total_seconds() == 0


def test_configuracion_tiene_prioridad():
    inicio = resolver_inicio(Path("VID_20261029_143015.mp4"), "2026-01-01T00:00:00", -5)
    assert inicio.year == 2026 and inicio.month == 1


def test_tiempo_con_tasa_constante_coincide_con_indice_entre_fps(tmp_path):
    ruta = tmp_path / "constante.avi"
    _video_sintetico(ruta, fotogramas=12, fps=10)
    with FuenteVideo(ruta) as fuente:
        fotogramas = list(fuente.fotogramas(cada_n=2))
    assert [f.indice for f in fotogramas] == [0, 2, 4, 6, 8, 10]
    for f in fotogramas:
        assert f.tiempo_s == pytest.approx(f.indice / 10, abs=1e-3)


def test_tiempo_con_tasa_variable_usa_la_marca_del_fotograma(tmp_path):
    fuente = _fuente_falsa(tmp_path, [0, 40, 70, 110, 200])
    tiempos = [f.tiempo_s for f in fuente.fotogramas()]
    assert tiempos == pytest.approx([0.0, 0.04, 0.07, 0.11, 0.2])


@pytest.mark.parametrize(
    "marcas_ms",
    [
        [0, 0, 0, 0],  # el contenedor no informa la marca
        [0, 40, 30, 120],  # marca que retrocede
    ],
)
def test_tiempo_vuelve_a_indice_entre_fps_si_la_marca_no_es_fiable(tmp_path, marcas_ms):
    fuente = _fuente_falsa(tmp_path, marcas_ms)
    tiempos = [f.tiempo_s for f in fuente.fotogramas()]
    assert tiempos == pytest.approx([0, 0.04, 0.08, 0.12])  # índice / 25 fps


def test_camara_usa_indice_entre_fps(tmp_path):
    fuente = _fuente_falsa(tmp_path, [0, 500, 1000])
    fuente.es_camara = True
    assert [f.tiempo_s for f in fuente.fotogramas()] == pytest.approx([0, 0.04, 0.08])


@pytest.mark.parametrize(
    ("rotacion", "esquina"),
    [
        (0, (slice(0, 8), slice(0, 8))),  # superior izquierda
        (90, (slice(0, 8), slice(-8, None))),  # superior derecha
        (180, (slice(-8, None), slice(-8, None))),  # inferior derecha
        (270, (slice(-8, None), slice(0, 8))),  # inferior izquierda
    ],
)
def test_rotacion_gira_cada_fotograma(tmp_path, rotacion, esquina):
    ruta = tmp_path / "rotar.avi"
    _video_sintetico(ruta, fotogramas=2, ancho=64, alto=48)
    with FuenteVideo(ruta, rotacion=rotacion) as fuente:
        imagen = next(fuente.fotogramas()).imagen
    assert imagen.shape[:2] == ((48, 64) if rotacion in (0, 180) else (64, 48))
    assert imagen[esquina].mean() > 200
    assert imagen.mean() < 30  # el resto sigue negro: el cuadro solo cambió de esquina


def test_rotacion_invalida(tmp_path):
    ruta = tmp_path / "rotar.avi"
    _video_sintetico(ruta, fotogramas=1)
    with pytest.raises(ValueError):
        FuenteVideo(ruta, rotacion=45)
