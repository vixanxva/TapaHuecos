"""Genera los datos de prueba: video sintético, imagen, GPX inventado y CSV de verdad de campo.

Todo es determinista y pesa pocos KB, así que no se versiona: se crea al vuelo.
Las pruebas lo llaman desde tests/conftest.py; también se puede correr a mano:

    python tests/fixtures/generar.py [carpeta]      # por defecto tests/fixtures/generados
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import gpxpy.gpx
import numpy as np
import pandas as pd

# El nombre lleva la hora de inicio: 14:30:10 en Colombia = 19:30:10 UTC, dentro del GPX.
NOMBRE_VIDEO = "VID_20261029_143010.avi"
INICIO_GPX = datetime(2026, 10, 29, 19, 30, 0, tzinfo=timezone.utc)
LAT0, LON0 = 8.75, -75.88  # Montería
PASO_LAT = 0.0001  # unos 11 m por segundo hacia el norte

ANCHO, ALTO = 640, 480
CENTRO_HUECO = (320, 240)
EJES_HUECO = (60, 40)


def cuadro_con_hueco(semilla: int = 0) -> np.ndarray:
    """Asfalto gris con textura y un hueco oscuro elíptico en el centro."""
    azar = np.random.default_rng(semilla)
    gris = np.clip(azar.normal(150, 6, (ALTO, ANCHO)), 0, 255).astype(np.uint8)
    cuadro = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
    cv2.ellipse(cuadro, CENTRO_HUECO, EJES_HUECO, 0, 0, 360, (50, 50, 50), -1)
    return cuadro


def video(ruta: Path, segundos: int = 3, fps: int = 10) -> Path:
    # MJPG en .avi: OpenCV lo escribe y lo lee en cualquier sistema sin códecs extra.
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), fps, (ANCHO, ALTO))
    for i in range(segundos * fps):
        escritor.write(cuadro_con_hueco(i))
    escritor.release()
    return ruta


def imagen(ruta: Path) -> Path:
    cv2.imwrite(str(ruta), cuadro_con_hueco())
    return ruta


def gpx(ruta: Path, segundos: int = 60) -> Path:
    """Recorrido recto hacia el norte, un punto por segundo."""
    recorrido = gpxpy.gpx.GPX()
    pista = gpxpy.gpx.GPXTrack()
    segmento = gpxpy.gpx.GPXTrackSegment()
    for s in range(segundos + 1):
        segmento.points.append(
            gpxpy.gpx.GPXTrackPoint(
                LAT0 + s * PASO_LAT, LON0, time=INICIO_GPX + timedelta(seconds=s)
            )
        )
    pista.segments.append(segmento)
    recorrido.tracks.append(pista)
    ruta.write_text(recorrido.to_xml(), encoding="utf-8")
    return ruta


def verdad_campo(ruta: Path) -> Path:
    """Dos huecos levantados en campo: uno donde pasa el video y otro 500 m al norte."""
    pd.DataFrame(
        [
            {"latitud": LAT0 + 10 * PASO_LAT, "longitud": LON0, "clase": "D40"},
            {"latitud": LAT0 + 0.0045, "longitud": LON0, "clase": "D40"},
        ]
    ).to_csv(ruta, index=False)
    return ruta


def generar(carpeta: Path) -> dict[str, Path]:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    return {
        "video": video(carpeta / NOMBRE_VIDEO),
        "imagen": imagen(carpeta / "hueco.jpg"),
        "gpx": gpx(carpeta / "recorrido.gpx"),
        "verdad": verdad_campo(carpeta / "verdad_campo.csv"),
    }


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "generados"
    for nombre, ruta in generar(destino).items():
        print(f"{nombre:7s} {ruta}")
