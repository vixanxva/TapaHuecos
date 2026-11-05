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
    rotacion: int = 0  # grados en sentido horario: 0, 90, 180 o 270
    region: list[float] | None = None  # [x1, y1, x2, y2] en fracciones del fotograma; None = completo


@dataclass
class ConfigSegmentacion:
    clahe_limite: float = 2.0
    clahe_rejilla: int = 8
    kernel_suavizado: int = 5
    kernel_morfologico: int = 5
    contraste_minimo: float = 4.0
    area_minima_px: int = 40
    clahe_tesela_min_px: int = 32
    fraccion_centro: float = 0.5
    # Huecos (D40)
    huecos_desborde_esquinas: float = 0.25
    huecos_nucleo_minimo: float = 0.65
    huecos_rareza_alta: float = 4.0
    huecos_rareza_baja: float = 2.0
    huecos_rareza_relativa: float = 0.3
    huecos_alternativa_nucleo: float = 0.15
    huecos_alternativa_esquinas: float = 0.3
    huecos_convexo_max: float = 1.3
    huecos_convexo_esquinas: float = 0.05
    huecos_halo_solidez: float = 0.9
    huecos_halo_area: float = 1.6
    huecos_rareza_lado_px: int = 155
    # Grietas (D00, D10)
    grieta_valle_dist_max: int = 4
    grieta_asimetria: float = 0.5
    grieta_asimetria_tolerancia: float = 2.0
    grieta_escala_percentil: float = 90.0
    grieta_escala_minima: float = 3.0
    grieta_pintura_delta: float = 20.0
    grieta_pintura_area_min: int = 30
    grieta_pintura_radio: int = 3
    grieta_pintura_frac: float = 0.3
    grieta_cuadrado_ratio: float = 1.5
    grieta_tramo_ventana: float = 0.06
    grieta_tramo_umbral: float = 1.5
    grieta_tramo_umbral_bajo: float = 1.15
    grieta_semilla_min: float = 1.0
    grieta_hueco_max: float = 0.2
    grieta_rama_exclusion: float = 0.15
    grieta_rama_umbral: float = 2.0
    grieta_rama_largo: float = 0.25
    grieta_crecer_umbral: float = 1.3
    grieta_crecer_pasos: int = 4
    # Piel de cocodrilo (D20)
    malla_lado_px: int = 192
    malla_iluminacion_px: int = 41
    malla_kernel_px: int = 5
    malla_pintura_min: float = 30.0
    malla_fraccion_grietas: float = 0.25
    malla_sigma_px: float = 12.0
    malla_densidad_rel: float = 0.7
    malla_sombra_rel: float = 0.65
    malla_sombra_azul: float = 0.1
    malla_vegetacion_verde: float = 30.0


@dataclass
class ConfigCalibracion:
    homografia: str | None = "calibracion/homografia.npy"
    metros_por_pixel: float | None = None


@dataclass
class ConfigRegistro:
    min_fotogramas: int = 3
    max_ausencia: int = 30
    tolerancia_gps_s: float = 5.0
    radio_fusion_m: float = 8.0


@dataclass
class Config:
    modelo: ConfigModelo = field(default_factory=ConfigModelo)
    video: ConfigVideo = field(default_factory=ConfigVideo)
    segmentacion: ConfigSegmentacion = field(default_factory=ConfigSegmentacion)
    calibracion: ConfigCalibracion = field(default_factory=ConfigCalibracion)
    registro: ConfigRegistro = field(default_factory=ConfigRegistro)


def validar_region(region: list[float] | None) -> None:
    if region is None:
        return
    if (
        len(region) != 4
        or not all(0 <= v <= 1 for v in region)
        or region[0] >= region[2]
        or region[1] >= region[3]
    ):
        raise ValueError(
            f"video.region debe ser [x1, y1, x2, y2] con 0 <= x1 < x2 <= 1 y 0 <= y1 < y2 <= 1; "
            f"se recibió {region}"
        )


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
