"""Etapa 3a: separar el daño dentro del recuadro de YOLO con OpenCV.

Recorte → escala de grises → CLAHE (contraste local) → suavizado gaussiano →
umbral → morfología → contornos → máscara binaria.

El umbral depende del tipo de daño:
- Huecos (D40): región oscura y compacta → umbral de Otsu invertido.
- Grietas (D00, D10): líneas finas → transformación black-hat, que resalta
  estructuras más oscuras y delgadas que el elemento estructurante, y luego Otsu.
- Piel de cocodrilo (D20): igual que grietas, más un cierre grande que une
  la malla en una sola región.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from tapahuecos.config import ConfigSegmentacion

MODO_POR_CLASE = {"D00": "linea", "D10": "linea", "D20": "malla", "D40": "region"}


@dataclass
class Segmentacion:
    mascara: np.ndarray  # uint8, 255 = daño, mismo tamaño que el recorte
    contornos: list[np.ndarray]  # en coordenadas del recorte

    @property
    def area_px(self) -> int:
        return int(cv2.countNonZero(self.mascara))


def _impar(n: int) -> int:
    n = max(int(n), 1)
    return n if n % 2 else n + 1


def _elipse(tamano: int) -> np.ndarray:
    tamano = _impar(tamano)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tamano, tamano))


def realzar(gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    """Mejora de la imagen: ecualización adaptativa (CLAHE) y suavizado gaussiano."""
    rejilla = max(1, cfg.clahe_rejilla)
    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_limite, tileGridSize=(rejilla, rejilla))
    k = _impar(cfg.kernel_suavizado)
    return cv2.GaussianBlur(clahe.apply(gris), (k, k), 0)


def segmentar(recorte: np.ndarray, codigo_clase: str, cfg: ConfigSegmentacion) -> Segmentacion:
    alto, ancho = recorte.shape[:2]
    vacia = np.zeros((alto, ancho), np.uint8)
    if alto < 3 or ancho < 3:
        return Segmentacion(vacia, [])

    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY) if recorte.ndim == 3 else recorte
    if float(gris.std()) < cfg.contraste_minimo:
        return Segmentacion(vacia, [])  # superficie uniforme: Otsu solo separaría ruido
    suave = realzar(gris, cfg)

    modo = MODO_POR_CLASE.get(codigo_clase, "region")
    limpieza = _elipse(cfg.kernel_morfologico)
    if modo == "region":
        _, binaria = cv2.threshold(suave, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, limpieza)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, limpieza)
    else:
        grande = _elipse(cfg.kernel_grietas)
        realce = cv2.morphologyEx(suave, cv2.MORPH_BLACKHAT, grande)
        _, binaria = cv2.threshold(realce, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        # Sin apertura: borraría las grietas finas.
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, limpieza)
        if modo == "malla":
            binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, grande)

    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contornos = [c for c in contornos if cv2.contourArea(c) >= cfg.area_minima_px]
    mascara = vacia
    if contornos:
        cv2.drawContours(mascara, contornos, -1, 255, cv2.FILLED)
    return Segmentacion(mascara, contornos)
