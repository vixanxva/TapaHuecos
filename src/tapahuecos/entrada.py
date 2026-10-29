"""Etapa 1: lectura del video fotograma por fotograma y hora de inicio de la grabación."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

# VID_20261029_143015.mp4 (Android), 20261029_143015.mp4 (Samsung), PXL_20261029_143015123.mp4 (Pixel).
# Los dígitos deben ir solos (fecha + hora + milisegundos opcionales) para no tomar trozos de otros números.
# VID-20261029-WA0001.mp4 (WhatsApp) no trae hora y no coincide.
_PATRON_FECHA = re.compile(r"(?<!\d)(20\d{6})[_-]?(\d{6})(?:\d{3})?(?!\d)")

# Grados en sentido horario → código de cv2.rotate
_ROTACIONES = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


@dataclass
class Fotograma:
    indice: int
    tiempo_s: float  # segundos desde el inicio del video
    imagen: np.ndarray


class FuenteVideo:
    """Archivo de video o cámara (índice entero) leído con OpenCV.

    OpenCV ya aplica la rotación guardada en los metadatos del video (CAP_PROP_ORIENTATION_AUTO
    está activo por defecto). `rotacion` (0, 90, 180 o 270, en sentido horario) es un giro
    adicional para videos sin metadatos o grabados con la cámara al revés.
    """

    def __init__(self, origen: str | Path | int, rotacion: int = 0):
        if rotacion not in (0, *_ROTACIONES):
            raise ValueError(f"rotacion debe ser 0, 90, 180 o 270, no {rotacion}")
        self.origen = origen
        self.rotacion = rotacion
        self.es_camara = isinstance(origen, int)
        self._cap = cv2.VideoCapture(origen if self.es_camara else str(origen))
        if not self._cap.isOpened():
            raise OSError(f"No se pudo abrir la fuente de video: {origen}")
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not self.es_camara else 0

    @property
    def duracion_s(self) -> float:
        return self.total / self.fps if self.total > 0 else 0.0

    def fotogramas(self, cada_n: int = 1) -> Iterator[Fotograma]:
        """Recorre el video entregando uno de cada `cada_n` fotogramas.

        `grab()` avanza sin decodificar, así que saltar fotogramas es barato.
        """
        cada_n = max(1, cada_n)
        indice = 0
        anterior = -1.0
        usar_marca = not self.es_camara
        while self._cap.grab():
            if usar_marca:
                # Tras grab(), POS_MSEC es la marca del fotograma recién capturado (no la del siguiente).
                # Con tasa variable (celulares) es más exacta que indice / fps.
                tiempo = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if tiempo < 0 or (indice > 0 and tiempo <= anterior):
                    log.warning(
                        "Marca de tiempo no fiable en el fotograma %d de %s; se usa índice / fps.",
                        indice, self.origen,
                    )
                    usar_marca = False
                anterior = tiempo
            if indice % cada_n == 0:
                ok, imagen = self._cap.retrieve()
                if ok:
                    if self.rotacion:
                        imagen = cv2.rotate(imagen, _ROTACIONES[self.rotacion])
                    yield Fotograma(indice, tiempo if usar_marca else indice / self.fps, imagen)
            indice += 1

    def cerrar(self) -> None:
        self._cap.release()

    def __enter__(self) -> FuenteVideo:
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


def _zona(utc_offset_horas: float) -> timezone:
    return timezone(timedelta(hours=utc_offset_horas))


def inicio_desde_nombre(nombre: str, utc_offset_horas: float) -> datetime | None:
    """Deduce la hora de inicio a partir del nombre que pone la cámara del celular."""
    coincidencia = _PATRON_FECHA.search(nombre)
    if not coincidencia:
        return None
    try:
        local = datetime.strptime("".join(coincidencia.groups()), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return local.replace(tzinfo=_zona(utc_offset_horas))


def interpretar_fecha(texto: str, utc_offset_horas: float) -> datetime:
    """ISO 8601; si no trae zona horaria se asume la hora local configurada."""
    fecha = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=_zona(utc_offset_horas))
    return fecha


def resolver_inicio(
    ruta_video: Path,
    inicio_config: str | None,
    utc_offset_horas: float,
    duracion_s: float = 0.0,
) -> datetime | None:
    """Hora (con zona) en que empezó la grabación, en orden de confiabilidad:

    1. la indicada en la configuración o por línea de comandos,
    2. la fecha del nombre del archivo,
    3. la fecha de modificación del archivo menos la duración (aproximada).
    """
    if inicio_config:
        return interpretar_fecha(inicio_config, utc_offset_horas)
    desde_nombre = inicio_desde_nombre(ruta_video.name, utc_offset_horas)
    if desde_nombre:
        return desde_nombre
    if ruta_video.exists():
        modificado = datetime.fromtimestamp(ruta_video.stat().st_mtime, tz=timezone.utc)
        log.warning(
            "No se pudo deducir la hora de inicio de %s; se estima con la fecha de modificación. "
            "Si los puntos quedan corridos en el mapa, use --inicio.",
            ruta_video.name,
        )
        return modificado - timedelta(seconds=duracion_s)
    return None
