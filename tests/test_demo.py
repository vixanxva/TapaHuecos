"""Pruebas de scripts/demo.py con imágenes sintéticas (sin YOLO)."""

import importlib.util
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from tapahuecos.clases import clase_por_codigo
from tapahuecos.config import Config
from tapahuecos.detector import Deteccion
from tapahuecos.entrada import FuenteVideo, inicio_desde_nombre
from tapahuecos.gps import Recorrido, distancia_m
from tapahuecos.pipeline import procesar
from tapahuecos.registro import BaseDatos

_RUTA_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo.py"
_spec = importlib.util.spec_from_file_location("demo", _RUTA_SCRIPT)
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

# Recuadro amplio alrededor de Montería
LAT_MIN, LAT_MAX = 8.70, 8.82
LON_MIN, LON_MAX = -75.95, -75.83
COLOMBIA = timezone(timedelta(hours=-5))


def _imagen(ruta, color=(90, 90, 90), ancho=120, alto=90):
    cuadro = np.full((alto, ancho, 3), color, np.uint8)
    cv2.ellipse(cuadro, (ancho // 2, alto * 2 // 3), (ancho // 6, alto // 8), 0, 0, 360, (30, 30, 30), -1)
    cv2.imwrite(str(ruta), cuadro)


def _dataset(raiz, estructura="images/split"):
    """Crea 2 imágenes con D40, 2 con D00 y 2 sin etiquetas. Devuelve la carpeta de imágenes."""
    if estructura == "images/split":
        imagenes, etiquetas = raiz / "images" / "test", raiz / "labels" / "test"
    else:
        imagenes, etiquetas = raiz / "test" / "images", raiz / "test" / "labels"
    imagenes.mkdir(parents=True)
    etiquetas.mkdir(parents=True)
    contenidos = {
        "hueco1": "3 0.5 0.6 0.2 0.1\n",
        "hueco2": "0 0.2 0.2 0.1 0.3\n3 0.5 0.6 0.2 0.1\n",
        "grieta1": "0 0.5 0.5 0.1 0.4\n",
        "grieta2": "1 0.5 0.5 0.4 0.1\n",
        "vacia1": "",
        "vacia2": None,  # sin archivo de etiquetas
    }
    for nombre, contenido in contenidos.items():
        _imagen(imagenes / f"{nombre}.jpg")
        if contenido is not None:
            (etiquetas / f"{nombre}.txt").write_text(contenido, encoding="utf-8")
    return imagenes


@pytest.mark.parametrize("estructura", ["images/split", "split/images"])
def test_seleccion_prefiere_huecos(tmp_path, estructura):
    carpeta = _dataset(tmp_path, estructura)
    elegidas = demo.seleccionar_imagenes(carpeta, 2, random.Random(0))
    assert {p.stem for p in elegidas} == {"hueco1", "hueco2"}

    elegidas = demo.seleccionar_imagenes(carpeta, 4, random.Random(0))
    assert {p.stem for p in elegidas} == {"hueco1", "hueco2", "grieta1", "grieta2"}


def test_seleccion_sin_etiquetas_toma_al_azar(tmp_path):
    for i in range(5):
        _imagen(tmp_path / f"foto{i}.png")
    (tmp_path / "notas.txt").write_text("no es imagen", encoding="utf-8")
    elegidas = demo.seleccionar_imagenes(tmp_path, 3, random.Random(1))
    assert len(elegidas) == 3 and len(set(elegidas)) == 3
    assert all(p.suffix == ".png" for p in elegidas)
    assert len(demo.seleccionar_imagenes(tmp_path, 50, random.Random(1))) == 5


@pytest.mark.parametrize("zoom", [1.0, 1.15])
def test_letterbox_respeta_tamano_y_proporcion(zoom):
    imagen = np.full((300, 400, 3), 200, np.uint8)  # 4:3 dentro de 16:9
    salida = demo.letterbox(imagen, 160, 90, zoom)
    assert salida.shape == (90, 160, 3)
    # 4:3 a 90 px de alto ocupa 120 px de ancho: franjas negras de 20 px a cada lado.
    assert salida[:, :20].max() == 0 and salida[:, 140:].max() == 0
    assert salida[:, 21:139].min() == 200


def test_zoom_agranda_y_baja_los_danos_de_la_parte_inferior():
    imagen = np.zeros((90, 120, 3), np.uint8)
    imagen[70:80, 55:65] = 255  # "hueco" en la parte inferior central
    imagen[:5] = 255  # franja de cielo arriba
    sin_zoom = demo.letterbox(imagen, 120, 90, 1.0)
    con_zoom = demo.letterbox(imagen, 120, 90, 1.15)

    def hueco(cuadro):
        filas, columnas = np.nonzero(cuadro[10:, :, 0] > 128)
        return len(filas), filas.mean() + 10, columnas.mean()

    area0, fila0, col0 = hueco(sin_zoom)
    area1, fila1, col1 = hueco(con_zoom)
    assert area1 > area0 and fila1 > fila0  # crece y baja, como al acercarse
    assert col1 == pytest.approx(col0, abs=0.5)  # sigue centrado
    assert con_zoom[:3, :, 0].max() < 128  # el cielo de arriba sale del cuadro


def test_video_tiene_los_fotogramas_esperados(tmp_path):
    imagenes = [np.full((60, 80, 3), v, np.uint8) for v in (80, 120, 160)]
    ruta = tmp_path / "VID_20261029_143000.mp4"
    n = demo.escribir_video(imagenes, ruta, 64, 48, fps=10, segundos_por_imagen=1.0, separacion=3)
    assert n == demo.total_fotogramas(3, 10, 3) == 36

    leidos = 0
    with FuenteVideo(ruta) as fuente:
        for fotograma in fuente.fotogramas():
            assert fotograma.imagen.shape == (48, 64, 3)
            leidos += 1
    assert leidos == 36


def test_valores_por_defecto_alcanzan_para_registrar():
    por_imagen = demo.fotogramas_por_imagen(2.0, 15)
    assert por_imagen == 30
    assert por_imagen // demo.CADA_N_FOTOGRAMAS >= demo.MIN_FOTOGRAMAS


def test_gpx_cubre_el_video_y_cae_en_monteria(tmp_path):
    inicio = datetime(2026, 10, 29, 14, 30, 0, tzinfo=COLOMBIA)
    duracion = 47.3
    ruta = demo.escribir_gpx(demo.puntos_gpx(inicio, duracion, 20.0), tmp_path / "demo.gpx")

    recorrido = Recorrido.desde_gpx(ruta)
    assert recorrido.inicio <= inicio
    assert recorrido.fin >= inicio + timedelta(seconds=duracion)
    assert recorrido.inicio.utcoffset() == timedelta(0)
    assert recorrido.inicio == datetime(2026, 10, 29, 19, 29, 55, tzinfo=timezone.utc)
    instantes = [p.instante for p in recorrido.puntos]
    assert {b - a for a, b in zip(instantes, instantes[1:], strict=False)} == {timedelta(seconds=1)}
    for p in recorrido.puntos:
        assert LAT_MIN < p.latitud < LAT_MAX and LON_MIN < p.longitud < LON_MAX

    # A 20 km/h avanza unos 5.6 m por segundo.
    a, b = recorrido.posicion(inicio), recorrido.posicion(inicio + timedelta(seconds=10))
    assert distancia_m(*a, *b) == pytest.approx(55.6, rel=0.05)


def test_gpx_ida_y_vuelta_si_la_ruta_se_acaba():
    ruta = ((8.75, -75.88), (8.751, -75.88))  # unos 111 m
    inicio = datetime(2026, 10, 29, 14, 30, 0, tzinfo=COLOMBIA)
    puntos = demo.puntos_gpx(inicio, 60, velocidad_kmh=18, margen_s=0, ruta=ruta)  # 5 m/s
    lats = [lat for _, lat, _ in puntos]
    assert max(lats) <= 8.751 + 1e-9 and min(lats) >= 8.75 - 1e-9
    assert lats[-1] < max(lats)  # ya viene de regreso


def test_nombre_del_video_da_la_hora_de_inicio():
    inicio = demo.resolver_inicio_local("2026-10-29T14:30:15", -5)
    nombre = demo.nombre_video(inicio)
    assert nombre == "VID_20261029_143015.mp4"
    assert inicio_desde_nombre(nombre, -5) == inicio
    assert inicio_desde_nombre(nombre, -5) == datetime(2026, 10, 29, 14, 30, 15, tzinfo=COLOMBIA)

    ahora = demo.resolver_inicio_local(None, -5)
    assert ahora.microsecond == 0
    assert inicio_desde_nombre(demo.nombre_video(ahora), -5) == ahora


class DetectorPorImagen:
    """Simula el seguidor: un hueco por imagen y un ID nuevo después de cada fotograma negro."""

    def __init__(self):
        self.track_id = 0
        self.en_negro = True

    def rastrear(self, imagen):
        if imagen.mean() < 5:
            self.en_negro = True
            return []
        if self.en_negro:
            self.track_id += 1
            self.en_negro = False
        return [Deteccion((40, 30, 120, 90), clase_por_codigo("D40"), 0.8, self.track_id)]


def test_demo_de_punta_a_punta(tmp_path, capsys):
    carpeta = _dataset(tmp_path / "rdd")
    destino = tmp_path / "demo"
    codigo = demo.main([
        "--imagenes", str(carpeta), "--destino", str(destino), "--cantidad", "3",
        "--tamano", "160x120", "--fps", "10", "--segundos-por-imagen", "1",
        "--inicio", "2026-10-29T14:30:00", "--semilla", "3",
    ])
    assert codigo == 0
    salida_consola = capsys.readouterr().out
    assert "tapahuecos procesar --video" in salida_consola and "DEMOSTRACIÓN" in salida_consola
    salida_consola.encode("cp1252")  # la consola de Windows debe poder mostrarlo

    video = destino / "VID_20261029_143000.mp4"
    gpx = destino / "VID_20261029_143000_demo.gpx"
    assert video.exists() and gpx.exists()

    cfg = Config()
    cfg.calibracion.homografia = None
    cfg.calibracion.metros_por_pixel = 0.005
    r = procesar(video, cfg, tmp_path / "salidas", gpx, detector=DetectorPorImagen())

    assert r.danos_registrados == 3
    with BaseDatos(r.base_datos) as bd:
        filas = bd.danos()
    assert len(filas) == 3
    for fila in filas:
        assert LAT_MIN < fila["latitud"] < LAT_MAX and LON_MIN < fila["longitud"] < LON_MAX
