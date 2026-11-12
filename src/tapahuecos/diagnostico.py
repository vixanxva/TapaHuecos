"""Comprobaciones previas: dependencias, modelo, calibración y video/GPX.

`tapahuecos verificar` usa este módulo para decir qué falta antes de procesar.
No carga YOLO ni procesa el video: solo comprueba que los insumos existan y que
el video y el GPX se puedan leer.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from tapahuecos.config import Config, validar_region
from tapahuecos.gps import Recorrido

Estado = Literal["ok", "aviso", "error"]


@dataclass(frozen=True)
class Comprobacion:
    nombre: str
    estado: Estado
    detalle: str


def _instalado(nombre: str) -> bool:
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError):
        return False


def _version(nombre: str) -> str | None:
    try:
        return importlib.metadata.version(nombre)
    except importlib.metadata.PackageNotFoundError:
        return None


def _comprobar_python() -> Comprobacion:
    # pyproject.toml exige >=3.10, así que aquí solo se informa la versión en uso.
    return Comprobacion("Python", "ok", sys.version.split()[0])


def _comprobar_config(ruta_config: Path | None) -> Comprobacion:
    if ruta_config is None:
        return Comprobacion("Configuración", "ok", "valores predeterminados (sin config.yaml)")
    if not Path(ruta_config).is_file():
        return Comprobacion("Configuración", "error", f"no existe {ruta_config}")
    return Comprobacion("Configuración", "ok", str(ruta_config))


def _comprobar_region(cfg: Config) -> Comprobacion:
    try:
        validar_region(cfg.video.region)
    except ValueError as error:
        return Comprobacion("Región de interés", "error", str(error))
    if cfg.video.region is None:
        return Comprobacion("Región de interés", "ok", "fotograma completo")
    return Comprobacion("Región de interés", "ok", str(cfg.video.region))


def _comprobar_modelo(cfg: Config) -> Comprobacion:
    pesos = Path(cfg.modelo.pesos)
    if pesos.is_file():
        tamano_mb = pesos.stat().st_size / 1_000_000
        return Comprobacion("Modelo", "ok", f"{pesos} ({tamano_mb:.1f} MB)")
    if pesos.parent == Path(".") and _MODELO_DESCARGABLE.match(pesos.name):
        # p. ej. yolov8n.pt: Ultralytics lo descarga solo la primera vez.
        return Comprobacion(
            "Modelo", "aviso",
            f"{pesos} no está en disco; Ultralytics lo descargará al procesar (requiere internet)",
        )
    detalle = f"no existe {pesos}"
    alternativa = pesos.parent / "best_rdd.pt"
    if pesos.name == "best.pt" and alternativa.is_file():
        detalle += f"; mientras falta best.pt use --pesos {alternativa.as_posix()}"
    return Comprobacion("Modelo", "error", detalle)


# Modelos preentrenados que Ultralytics descarga por nombre (yolov8n.pt, yolo11s.pt…).
_MODELO_DESCARGABLE = re.compile(r"^yolo(v\d+|\d+)[nsmlx]?(-seg)?\.pt$", re.IGNORECASE)


def _comprobar_calibracion(cfg: Config) -> Comprobacion:
    homografia = Path(cfg.calibracion.homografia) if cfg.calibracion.homografia else None
    if homografia is not None and homografia.is_file():
        return Comprobacion("Calibración", "ok", f"homografía {homografia}")
    if cfg.calibracion.metros_por_pixel is not None:
        if cfg.calibracion.metros_por_pixel <= 0:
            return Comprobacion(
                "Calibración", "error", "metros_por_pixel debe ser mayor que 0"
            )
        return Comprobacion(
            "Calibración", "ok",
            f"metros_por_pixel={cfg.calibracion.metros_por_pixel:g} (aproximada)",
        )
    detalle = "sin homografía ni metros_por_pixel: el área quedará solo en píxeles"
    if homografia is not None:
        detalle += f" (no existe {homografia})"
    return Comprobacion("Calibración", "aviso", detalle)


def _comprobar_mapa(cfg: Config) -> Comprobacion:
    from tapahuecos.salidas import capa_de_mosaicos

    try:
        capa_de_mosaicos(cfg.mapa.tiles)
    except ValueError as error:
        return Comprobacion("Mapa", "error", str(error))
    return Comprobacion("Mapa", "ok", f"mosaicos {cfg.mapa.tiles}")


def _comprobar_yolo() -> Comprobacion:
    if not _instalado("ultralytics"):
        return Comprobacion(
            "Ultralytics", "error",
            'no está instalado; ejecute: pip install -e ".[yolo]"',
        )
    version = _version("ultralytics")
    return Comprobacion("Ultralytics", "ok", f"instalado {version or ''}".strip())


def _comprobar_torch() -> Comprobacion:
    try:
        import torch
    except Exception as error:  # puede fallar por DLLs o por una instalación incompleta
        return Comprobacion("PyTorch", "error", f"no se pudo importar: {error}")
    dispositivo = "GPU CUDA disponible" if torch.cuda.is_available() else "CPU (sin CUDA)"
    return Comprobacion("PyTorch", "ok", f"{torch.__version__}; {dispositivo}")


def _comprobar_video(
    ruta: Path, cfg: Config
) -> tuple[Comprobacion, datetime | None, float]:
    from tapahuecos.entrada import resolver_inicio

    if not ruta.is_file():
        return Comprobacion("Video", "error", f"no existe {ruta}"), None, 0.0

    import cv2

    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        return Comprobacion(
            "Video", "error", f"OpenCV no pudo abrir {ruta} (¿está dañado o incompleto?)"
        ), None, 0.0
    try:
        fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        captura.release()

    duracion = total / fps if total > 0 else 0.0
    try:
        inicio = resolver_inicio(
            ruta, cfg.video.inicio_grabacion, cfg.video.utc_offset_horas, duracion
        )
    except ValueError as error:
        return Comprobacion(
            "Video", "error", f"hora de inicio inválida (video.inicio_grabacion): {error}"
        ), None, duracion
    detalle = f"{ancho}x{alto}, {duracion:.1f} s, {fps:.1f} fps"
    if inicio is not None:
        detalle += f", inicio {inicio.isoformat(timespec='seconds')}"
    return Comprobacion("Video", "ok", detalle), inicio, duracion


def _comprobar_gpx(ruta: Path) -> tuple[Comprobacion, Recorrido | None]:
    if not ruta.is_file():
        return Comprobacion("GPX", "error", f"no existe {ruta}"), None
    try:
        recorrido = Recorrido.desde_gpx(ruta)
    except Exception as error:
        return Comprobacion("GPX", "error", f"no se pudo leer {ruta}: {error}"), None
    detalle = (
        f"{len(recorrido.puntos)} puntos, "
        f"{recorrido.inicio.isoformat(timespec='seconds')} a "
        f"{recorrido.fin.isoformat(timespec='seconds')}"
    )
    return Comprobacion("GPX", "ok", detalle), recorrido


def _comprobar_solape(
    inicio: datetime, duracion: float, recorrido: Recorrido
) -> Comprobacion:
    fin = inicio + timedelta(seconds=duracion)
    if fin < recorrido.inicio or inicio > recorrido.fin:
        return Comprobacion(
            "Solape video/GPX", "aviso",
            f"el video ({inicio.isoformat(timespec='seconds')} a "
            f"{fin.isoformat(timespec='seconds')}) no coincide con el GPX "
            f"({recorrido.inicio.isoformat(timespec='seconds')} a "
            f"{recorrido.fin.isoformat(timespec='seconds')}); los daños quedarán sin "
            "coordenadas. Revise --inicio, utc_offset_horas o use el GPX de ese video.",
        )
    return Comprobacion(
        "Solape video/GPX", "ok",
        f"el video cabe entre {recorrido.inicio.isoformat(timespec='seconds')} y "
        f"{recorrido.fin.isoformat(timespec='seconds')}",
    )


def comprobar_entorno(
    cfg: Config,
    ruta_config: Path | None = None,
    ruta_video: Path | None = None,
    ruta_gpx: Path | None = None,
) -> list[Comprobacion]:
    """Revisa lo necesario para `procesar`; los datos inválidos se informan como error."""
    comprobaciones = [
        _comprobar_python(),
        _comprobar_config(ruta_config),
        _comprobar_region(cfg),
        _comprobar_modelo(cfg),
        _comprobar_calibracion(cfg),
        _comprobar_mapa(cfg),
    ]
    yolo = _comprobar_yolo()
    comprobaciones.append(yolo)
    if yolo.estado == "ok":
        comprobaciones.append(_comprobar_torch())

    inicio = duracion = None
    if ruta_video is not None:
        video, inicio, duracion = _comprobar_video(Path(ruta_video), cfg)
        comprobaciones.append(video)

    recorrido = None
    if ruta_gpx is not None:
        gpx, recorrido = _comprobar_gpx(Path(ruta_gpx))
        comprobaciones.append(gpx)

    if inicio is not None and recorrido is not None and duracion is not None:
        comprobaciones.append(_comprobar_solape(inicio, duracion, recorrido))
    elif ruta_video is not None and ruta_gpx is None:
        comprobaciones.append(
            Comprobacion(
                "GPX", "aviso",
                "sin --gpx: los daños se registrarán sin coordenadas",
            )
        )
    return comprobaciones
