"""Etapa 3b: conversión del área de píxeles a metros cuadrados.

Con una homografía (transformación proyectiva imagen → plano de la vía) cada
contorno se lleva a coordenadas del suelo en metros y allí se mide su área.
Esto corrige la perspectiva: un hueco lejano ocupa menos píxeles que uno cercano
del mismo tamaño. La homografía solo es válida para puntos sobre la vía y con la
cámara montada siempre en la misma posición.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from tapahuecos.config import ConfigCalibracion

log = logging.getLogger(__name__)


class Medidor:
    def __init__(self, homografia: np.ndarray | None = None, metros_por_pixel: float | None = None):
        self.homografia = homografia
        self.metros_por_pixel = metros_por_pixel

    @classmethod
    def desde_config(cls, cfg: ConfigCalibracion) -> Medidor:
        homografia = None
        if cfg.homografia and Path(cfg.homografia).exists():
            homografia = np.load(cfg.homografia)
        elif cfg.metros_por_pixel is None:
            log.warning(
                "Sin calibración: el área solo se reportará en píxeles. "
                "Ejecute scripts/calibrar_homografia.py para obtener m²."
            )
        return cls(homografia, cfg.metros_por_pixel)

    @property
    def calibrado(self) -> bool:
        return self.homografia is not None or self.metros_por_pixel is not None

    def area_m2(self, contornos: list[np.ndarray]) -> float | None:
        """Área total en m² de contornos expresados en coordenadas del fotograma completo."""
        if not self.calibrado:
            return None
        if self.homografia is not None:
            total = 0.0
            for contorno in contornos:
                puntos = contorno.reshape(-1, 1, 2).astype(np.float32)
                en_suelo = cv2.perspectiveTransform(puntos, self.homografia)
                total += abs(cv2.contourArea(en_suelo))
            return total
        return sum(cv2.contourArea(c) for c in contornos) * self.metros_por_pixel**2
