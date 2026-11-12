"""Pruebas de la configuración: valores por defecto, lectura del YAML y mosaicos del mapa."""

from __future__ import annotations

import pytest

from tapahuecos.config import Config, cargar_config
from tapahuecos.salidas import TILES_PREDETERMINADOS, capa_de_mosaicos, generar_mapa


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


def _fila_con_gps() -> dict:
    return {
        "id": 1, "clase": "D40", "nombre_clase": "Hueco", "confianza": 0.5,
        "area_m2": None, "area_px": 10, "instante_utc": None, "video": "v.mp4",
        "tiempo_video_s": 0.0, "latitud": 8.76, "longitud": -75.88,
        "recorte": "r.jpg", "verificado": None,
    }


def test_generar_mapa_acepta_una_url_propia(tmp_path):
    # config.yaml ofrece "una URL propia con {z}/{x}/{y}"; folium exige atribución.
    url = "https://mosaicos.example.org/{z}/{x}/{y}.png"
    ruta = generar_mapa([_fila_con_gps()], tmp_path / "mapa.html", tmp_path, url)
    html = ruta.read_text(encoding="utf-8")
    assert "mosaicos.example.org" in html


def test_mosaicos_desconocidos_dan_un_error_claro():
    with pytest.raises(ValueError, match="mapa.tiles"):
        capa_de_mosaicos("openstreetmapp")


def test_procesar_rechaza_mosaicos_invalidos_antes_de_empezar(tmp_path):
    from tapahuecos.pipeline import procesar

    cfg = Config()
    cfg.mapa.tiles = "Esri.NoExiste"

    class DetectorQueNoSeDebeUsar:
        def detectar(self, *_args, **_kwargs):
            raise AssertionError("no debió llegar a procesar fotogramas")

    with pytest.raises(ValueError, match="mapa.tiles"):
        procesar(tmp_path / "no-importa.mp4", cfg, tmp_path / "salida",
                 detector=DetectorQueNoSeDebeUsar())
    assert not (tmp_path / "salida").exists()


def test_verificar_informa_mosaicos_invalidos():
    from tapahuecos.diagnostico import comprobar_entorno

    cfg = Config()
    cfg.mapa.tiles = "Esri.NoExiste"
    mapa = next(c for c in comprobar_entorno(cfg) if c.nombre == "Mapa")
    assert mapa.estado == "error"
    assert next(c for c in comprobar_entorno(Config()) if c.nombre == "Mapa").estado == "ok"
