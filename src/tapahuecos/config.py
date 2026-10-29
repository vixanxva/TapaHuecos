"""Carga de la configuración (config.yaml) con valores predeterminados."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ConfigModelo:
    pesos: str = "modelos/best.pt"
    confianza: float = 0.35
    iou: float = 0.5
    tamano_imagen: int = 640
    tracker: str = "bytetrack.yaml"
    dispositivo: str | None = None


@dataclass
class ConfigVideo:
    cada_n_fotogramas: int = 2
    inicio_grabacion: str | None = None
    utc_offset_horas: float = -5.0
    desfase_gps_s: float = 0.0


@dataclass
class ConfigSegmentacion:
    clahe_limite: float = 2.0
    clahe_rejilla: int = 8
    kernel_suavizado: int = 5
    kernel_morfologico: int = 5
    kernel_grietas: int = 15
    contraste_minimo: float = 4.0
    area_minima_px: int = 40


@dataclass
class ConfigCalibracion:
    homografia: str | None = "calibracion/homografia.npy"
    metros_por_pixel: float | None = None


@dataclass
class ConfigRegistro:
    min_fotogramas: int = 3
    max_ausencia: int = 30
    tolerancia_gps_s: float = 5.0


@dataclass
class Config:
    modelo: ConfigModelo = field(default_factory=ConfigModelo)
    video: ConfigVideo = field(default_factory=ConfigVideo)
    segmentacion: ConfigSegmentacion = field(default_factory=ConfigSegmentacion)
    calibracion: ConfigCalibracion = field(default_factory=ConfigCalibracion)
    registro: ConfigRegistro = field(default_factory=ConfigRegistro)


def _seccion(tipo: type, datos: dict[str, Any], nombre: str):
    try:
        return tipo(**(datos.get(nombre) or {}))
    except TypeError as error:
        raise ValueError(f"Configuración inválida en la sección '{nombre}': {error}") from error


def cargar_config(ruta: str | Path | None = None) -> Config:
    """Lee un archivo YAML; las claves que falten toman su valor predeterminado."""
    if ruta is None:
        return Config()
    with open(ruta, encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or {}
    desconocidas = set(datos) - set(Config.__dataclass_fields__)
    if desconocidas:
        raise ValueError(f"Secciones desconocidas en {ruta}: {sorted(desconocidas)}")
    return Config(
        modelo=_seccion(ConfigModelo, datos, "modelo"),
        video=_seccion(ConfigVideo, datos, "video"),
        segmentacion=_seccion(ConfigSegmentacion, datos, "segmentacion"),
        calibracion=_seccion(ConfigCalibracion, datos, "calibracion"),
        registro=_seccion(ConfigRegistro, datos, "registro"),
    )
