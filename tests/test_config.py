"""Pruebas de la configuración: valores por defecto, lectura del YAML y mosaicos del mapa."""

from __future__ import annotations

import pytest

from tapahuecos.config import Config, cargar_config
from tapahuecos.salidas import TILES_PREDETERMINADOS, generar_mapa


def test_mosaicos_por_defecto_no_exigen_clave():
    # Esri no pide clave; CARTO ahora sí y OpenStreetMap bloquea por política de uso.
    assert Config().mapa.tiles == "Esri.WorldStreetMap"
    assert TILES_PREDETERMINADOS == "Esri.WorldStreetMap"


def test_config_lee_la_seccion_mapa(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text('mapa:\n  tiles: "OpenTopoMap"\n', encoding="utf-8")
    assert cargar_config(ruta).mapa.tiles == "OpenTopoMap"


def test_config_rechaza_claves_desconocidas_en_mapa(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text('mapa:\n  mosaicos: "x"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_config(ruta)


def test_generar_mapa_usa_los_mosaicos_indicados(tmp_path):
    filas = [
        {
            "id": 1, "clase": "D40", "nombre_clase": "Hueco", "confianza": 0.5,
            "area_m2": None, "area_px": 10, "instante_utc": None, "video": "v.mp4",
            "tiempo_video_s": 0.0, "latitud": 8.76, "longitud": -75.88,
            "recorte": "r.jpg", "verificado": None,
        }
    ]
    ruta = generar_mapa(filas, tmp_path / "mapa.html", tmp_path, "OpenTopoMap")
    assert "opentopomap" in ruta.read_text(encoding="utf-8")
