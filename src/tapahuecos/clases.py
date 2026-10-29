"""Clases de daño del dataset RDD2022 usadas por el detector."""

from __future__ import annotations

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
    return ClaseDano(codigo, codigo, "Clase no estándar", (160, 160, 160), "#a0a0a0")
