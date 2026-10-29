"""Correcciones encontradas al procesar un video real con un modelo YOLO genérico."""

import math

import numpy as np

from tapahuecos.clases import CLASES, clase_por_codigo
from tapahuecos.config import ConfigSegmentacion
from tapahuecos.registro import BaseDatos, GestorDanos, Observacion
from tapahuecos.salidas import resumen
from tapahuecos.segmentacion import segmentar


def _obs(caja, area_m2=None):
    return Observacion(
        track_id=np.int64(4), clase=clase_por_codigo("D40"), confianza=0.7, fotograma=0,
        tiempo_video_s=0.0, instante_utc=None, latitud=None, longitud=None,
        area_px=np.int64(120), area_m2=area_m2, caja=caja, recorte=np.zeros((5, 5, 3), np.uint8),
    )


def test_coordenadas_numpy_se_guardan_como_enteros(tmp_path):
    # YOLO entrega int64 de NumPy; SQLite los guardaba como bytes.
    caja = tuple(np.array([881, 1016, 1041, 1507], dtype=np.int64))
    with BaseDatos(tmp_path / "danos.db") as bd:
        rid = bd.nuevo_recorrido("v.mp4", None, "best.pt")
        gestor = GestorDanos(bd, rid, tmp_path / "recortes", min_fotogramas=1)
        gestor.observar(_obs(caja))
        gestor.finalizar()
        (fila,) = bd.danos()
    assert (fila["x1"], fila["y1"], fila["x2"], fila["y2"]) == (881, 1016, 1041, 1507)
    assert all(type(fila[k]) is int for k in ("x1", "y1", "x2", "y2", "track_id", "area_px"))


def test_clases_genericas_tienen_color_propio():
    persona, moto = clase_por_codigo("person"), clase_por_codigo("motorcycle")
    assert persona.color_bgr != (160, 160, 160)
    assert persona == clase_por_codigo("person")  # siempre el mismo color para el mismo nombre
    assert persona.color_hex.startswith("#") and len(persona.color_hex) == 7
    assert {persona.codigo, moto.codigo}.isdisjoint(c.codigo for c in CLASES)


def test_clases_genericas_no_se_segmentan():
    imagen = np.full((100, 100, 3), 150, np.uint8)
    imagen[30:70, 30:70] = 40
    assert segmentar(imagen, "person", ConfigSegmentacion()).area_px == 0
    assert segmentar(imagen, "D40", ConfigSegmentacion()).area_px > 0


def test_resumen_sin_calibracion_deja_el_area_vacia():
    filas = [
        {"id": 1, "clase": "D40", "nombre_clase": "Hueco", "area_m2": None, "latitud": None,
         "verificado": None, "grupo": None},
    ]
    tabla = resumen(filas)
    assert math.isnan(tabla.loc[0, "area_total_m2"])
