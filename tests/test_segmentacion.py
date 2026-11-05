import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from tapahuecos.config import ConfigSegmentacion
from tapahuecos.medicion import Medidor
from tapahuecos.segmentacion import segmentar

DATOS = Path(__file__).parent / "datos"


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


def test_hueco_mas_claro_que_el_entorno():
    # Mancha clara del pavimento, base expuesta o agua que refleja el cielo: el hueco no es
    # oscuro y un Otsu invertido marcaría el asfalto de alrededor (daños #30 y #59 de la #37).
    imagen = _asfalto(semilla=1)
    cv2.ellipse(imagen, (100, 100), (50, 30), 0, 0, 360, (215, 215, 215), -1)
    seg = segmentar(imagen, "D40", ConfigSegmentacion())
    assert seg.area_px == pytest.approx(math.pi * 50 * 30, rel=0.15)
    assert seg.mascara[100, 100] == 255
    assert seg.mascara[5, 5] == 0


def test_hueco_descarta_regiones_lejos_del_centro():
    imagen = _asfalto(semilla=2)
    cv2.ellipse(imagen, (100, 100), (40, 25), 0, 0, 360, (60, 60, 60), -1)
    cv2.rectangle(imagen, (0, 0), (30, 30), (60, 60, 60), -1)  # mancha oscura en la esquina
    seg = segmentar(imagen, "D40", ConfigSegmentacion())
    assert seg.mascara[100, 100] == 255
    assert seg.mascara[10, 10] == 0


def test_grieta_entre_marcas_viales():
    # Entre dos líneas pintadas cercanas (doble línea, paso de peatones) el black-hat veía
    # un valle oscuro y lo marcaba como grieta.
    imagen = _asfalto(semilla=3)
    cv2.rectangle(imagen, (30, 0), (45, 199), (235, 235, 235), -1)
    cv2.rectangle(imagen, (56, 0), (71, 199), (235, 235, 235), -1)
    cv2.line(imagen, (140, 20), (140, 180), (70, 70, 70), 3)
    seg = segmentar(imagen, "D00", ConfigSegmentacion())
    assert seg.mascara[100, 140] == 255
    assert not seg.mascara[:, 46:56].any()


def test_grieta_no_se_desborda_en_asfalto_rugoso():
    # Con Otsu sobre el black-hat, la textura del asfalto ocupaba medio recuadro.
    grano = cv2.GaussianBlur(np.random.default_rng(4).normal(0, 1, (200, 200)), (0, 0), 1.5)
    gris = np.clip(150 + grano / grano.std() * 12, 0, 255).astype(np.uint8)
    imagen = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
    cv2.line(imagen, (30, 30), (170, 170), (60, 60, 60), 3)
    seg = segmentar(imagen, "D10", ConfigSegmentacion())
    assert seg.mascara[100, 100] == 255
    assert seg.area_px < 0.08 * 200 * 200


def test_grieta_punteada_se_conserva():
    imagen = _asfalto(semilla=5)
    for y in range(20, 180, 16):
        cv2.line(imagen, (100, y), (100, y + 8), (70, 70, 70), 2)
    seg = segmentar(imagen, "D00", ConfigSegmentacion())
    tramos = [y for y in range(20, 180, 16) if seg.mascara[y + 4, 98:103].any()]
    assert len(tramos) >= 8


# Recortes reales de RDD2022 (licencia y fuente en tests/datos/README.md). Cada uno fallaba
# con la segmentación anterior; las comprobaciones son de comportamiento, no de píxeles exactos.
def _recorte_real(nombre):
    imagen = cv2.imread(str(DATOS / nombre))
    assert imagen is not None, nombre
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    return imagen, gris


def _anillo_borde(forma, fraccion=0.15):
    alto, ancho = forma
    anillo = np.ones(forma, bool)
    my, mx = round(alto * fraccion), round(ancho * fraccion)
    anillo[my:alto - my, mx:ancho - mx] = False
    return anillo


@pytest.mark.parametrize(
    "nombre, claro",
    [
        ("d40_hueco_claro_japan_012290.jpg", True),  # antes marcaba el asfalto de alrededor
        ("d40_hueco_claro_pequeno_japan_010295.jpg", True),  # ídem, recorte de 43 × 26 px
        ("d40_hueco_con_agua_india_003761.jpg", True),  # antes cubría el 90 % del recuadro
        ("d40_hueco_delgado_japan_011590.jpg", False),  # antes la apertura lo borraba entero
    ],
)
def test_huecos_reales(nombre, claro):
    imagen, gris = _recorte_real(nombre)
    mascara = segmentar(imagen, "D40", ConfigSegmentacion()).mascara > 0
    alto, ancho = mascara.shape
    assert mascara[alto // 2, ancho // 2]
    assert 0.1 < mascara.mean() < 0.6
    assert mascara[_anillo_borde(mascara.shape)].mean() < 0.4
    dentro, fuera = gris[mascara].mean(), gris[~mascara].mean()
    assert (dentro > fuera) if claro else (dentro < fuera)


@pytest.mark.parametrize(
    "nombre",
    [
        "d00_grieta_larga_us_000575.jpg",  # antes cubría un tercio del recuadro
        "d00_grieta_japan_006566.jpg",  # antes, más de la mitad
        "d10_grieta_gruesa_japan_005615.jpg",  # antes, tres cuartos
        "d10_grieta_marcas_viales_us_000919.jpg",  # antes marcaba los bordes de las líneas
    ],
)
def test_grietas_reales(nombre):
    imagen, gris = _recorte_real(nombre)
    mascara = segmentar(imagen, nombre[:3].upper(), ConfigSegmentacion()).mascara > 0
    assert 0 < mascara.mean() < 0.15
    # La máscara sigue lo oscuro (la grieta), no la textura ni los bordes de lo claro.
    assert gris[mascara].mean() < gris[~mascara].mean() - 10
    brillo = cv2.dilate((gris > np.percentile(gris, 97)).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    assert (mascara & brillo).sum() < 0.4 * mascara.sum()
