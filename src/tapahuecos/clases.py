"""Clases de daño del dataset RDD2022 usadas por el detector."""

from __future__ import annotations

import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaseDano:
    codigo: str
    nombre: str
    descripcion: str
    color_bgr: tuple[int, int, int]  # para OpenCV
    color_hex: str  # para el mapa


CLASES: tuple[ClaseDano, ...] = (
    ClaseDano(
        "D00",
        "Grieta longitudinal",
        "Línea a lo largo del sentido de la vía",
        (0, 200, 255),
        "#ffc800",
    ),
    ClaseDano(
        "D10",
        "Grieta transversal",
        "Línea perpendicular al sentido de la vía",
        (255, 160, 0),
        "#00a0ff",
    ),
    ClaseDano(
        "D20",
        "Piel de cocodrilo",
        "Red de grietas entrelazadas en forma de malla",
        (200, 0, 200),
        "#c800c8",
    ),
    ClaseDano(
        "D40",
        "Hueco",
        "Cavidad con bordes definidos; suele verse más oscura o con agua",
        (0, 0, 255),
        "#ff0000",
    ),
)

CODIGOS: tuple[str, ...] = tuple(c.codigo for c in CLASES)
_POR_CODIGO = {c.codigo: c for c in CLASES}


def clase_por_codigo(codigo: str) -> ClaseDano:
    """Devuelve la clase con ese código; si el modelo usa otro nombre, crea una genérica."""
    codigo = codigo.strip()
    if codigo in _POR_CODIGO:
        return _POR_CODIGO[codigo]
    # Color fijo por nombre, para que cada clase de un modelo genérico se distinga en el video.
    hexa = _COLORES_GENERICOS[zlib.crc32(codigo.encode()) % len(_COLORES_GENERICOS)]
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return ClaseDano(codigo, codigo, "Clase no estándar", (b, g, r), hexa)


_COLORES_GENERICOS = ("#00c853", "#2979ff", "#ff6d00", "#d500f9", "#00b8d4", "#ffd600", "#ff1744")
