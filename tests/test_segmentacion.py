import math

import cv2
import numpy as np
import pytest

from tapahuecos.config import ConfigSegmentacion
from tapahuecos.medicion import Medidor
from tapahuecos.segmentacion import segmentar


def _asfalto(alto=200, ancho=200, semilla=0):
    azar = np.random.default_rng(semilla)
    gris = np.clip(azar.normal(150, 6, (alto, ancho)), 0, 255).astype(np.uint8)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


def test_hueco_area_aproximada():
    imagen = _asfalto()
    cv2.ellipse(imagen, (100, 100), (50, 30), 0, 0, 360, (60, 60, 60), -1)
    seg = segmentar(imagen, "D40", ConfigSegmentacion())
    esperado = math.pi * 50 * 30
    assert seg.area_px == pytest.approx(esperado, rel=0.15)
    assert seg.mascara[100, 100] == 255
    assert seg.mascara[5, 5] == 0


def test_grieta_fina():
    imagen = _asfalto()
    cv2.line(imagen, (100, 20), (100, 180), (70, 70, 70), 3)
    seg = segmentar(imagen, "D00", ConfigSegmentacion())
    assert 300 < seg.area_px < 2500
    assert seg.mascara[100, 100] == 255
    assert seg.mascara[100, 30] == 0


def test_superficie_uniforme_no_segmenta():
    imagen = np.full((100, 100, 3), 150, np.uint8)
    assert segmentar(imagen, "D40", ConfigSegmentacion()).area_px == 0


def test_recorte_degenerado():
    assert segmentar(np.zeros((2, 50, 3), np.uint8), "D40", ConfigSegmentacion()).area_px == 0


def test_area_con_homografia():
    # 1 píxel = 1 cm → un cuadrado de 100 × 100 px mide 1 m²
    medidor = Medidor(homografia=np.diag([0.01, 0.01, 1.0]))
    cuadrado = np.array([[[0, 0]], [[100, 0]], [[100, 100]], [[0, 100]]], dtype=np.int32)
    assert medidor.area_m2([cuadrado]) == pytest.approx(1.0)


def test_area_sin_calibrar():
    assert Medidor().area_m2([]) is None
    assert Medidor(metros_por_pixel=0.01).area_m2([]) == 0.0
