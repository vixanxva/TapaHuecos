"""Prueba de punta a punta con un video sintético y un detector simulado (sin YOLO)."""

import cv2
import numpy as np

from tapahuecos.clases import clase_por_codigo
from tapahuecos.config import Config
from tapahuecos.detector import Deteccion
from tapahuecos.pipeline import procesar


class DetectorFalso:
    """Siempre ve el mismo hueco en el centro, con ID de seguimiento 7."""

    def rastrear(self, imagen):
        return [Deteccion((220, 140, 420, 340), clase_por_codigo("D40"), 0.8, 7)]


def _video_sintetico(ruta, segundos=3, fps=10):
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 480))
    azar = np.random.default_rng(0)
    for _ in range(segundos * fps):
        cuadro = np.clip(azar.normal(150, 6, (480, 640)), 0, 255).astype(np.uint8)
        cuadro = cv2.cvtColor(cuadro, cv2.COLOR_GRAY2BGR)
        cv2.ellipse(cuadro, (320, 240), (60, 40), 0, 0, 360, (50, 50, 50), -1)
        escritor.write(cuadro)
    escritor.release()


def test_procesar_genera_todas_las_salidas(tmp_path, gpx_recto):
    ruta_gpx, _ = gpx_recto
    video = tmp_path / "VID_20261029_143010.avi"  # 19:30:10 UTC → dentro del GPX
    _video_sintetico(video)

    cfg = Config()
    cfg.calibracion.homografia = None
    cfg.calibracion.metros_por_pixel = 0.005
    salida = tmp_path / "salidas"

    r = procesar(video, cfg, salida, ruta_gpx, detector=DetectorFalso())

    assert r.fotogramas_procesados == 15  # 30 fotogramas, 1 de cada 2
    assert r.danos_registrados == 1
    assert r.video_anotado.exists() and r.mapa.exists() and r.csv.exists()
    assert len(list((salida / "recortes").glob("*.jpg"))) == 1

    from tapahuecos.registro import BaseDatos

    with BaseDatos(r.base_datos) as bd:
        (fila,) = bd.danos()
    assert fila["clase"] == "D40"
    assert abs(fila["latitud"] - (8.75 + 10 * 0.0001)) < 0.0005
    esperado_m2 = np.pi * 60 * 40 * 0.005**2
    assert abs(fila["area_m2"] - esperado_m2) / esperado_m2 < 0.2
    assert "recortes/" in r.mapa.read_text(encoding="utf-8")
