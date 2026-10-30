"""Prueba de punta a punta de la consola (`tapahuecos ...`) sobre los datos de tests/fixtures.

YOLO se reemplaza por un detector simulado; todo lo demás es el código real.
"""

import pandas as pd
import pytest

import tapahuecos.detector
from tapahuecos.clases import clase_por_codigo
from tapahuecos.cli import main
from tapahuecos.detector import Deteccion
from tapahuecos.evaluacion import evaluar_campo
from tapahuecos.registro import BaseDatos

COLUMNAS_CSV = {
    "id", "recorrido_id", "track_id", "clase", "nombre_clase", "confianza", "veces_visto",
    "fotograma", "tiempo_video_s", "instante_utc", "latitud", "longitud", "area_px", "area_m2",
    "x1", "y1", "x2", "y2", "recorte", "verificado", "grupo", "video",
}


class DetectorSimulado:
    """Misma firma que Detector(cfg): ve siempre el hueco del video sintético."""

    def __init__(self, cfg):
        self.cfg = cfg

    def rastrear(self, imagen):
        return [Deteccion((220, 140, 420, 340), clase_por_codigo("D40"), 0.8, 1)]


@pytest.fixture
def config_yaml(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text(
        "calibracion:\n  homografia: null\n  metros_por_pixel: 0.005\n", encoding="utf-8"
    )
    return ruta


def test_procesar_y_comandos_sobre_fixtures(tmp_path, datos_prueba, config_yaml, monkeypatch):
    monkeypatch.setattr(tapahuecos.detector, "Detector", DetectorSimulado)
    salida = tmp_path / "salidas"

    codigo = main([
        "procesar", "--video", str(datos_prueba["video"]), "--gpx", str(datos_prueba["gpx"]),
        "--config", str(config_yaml), "--salida", str(salida),
    ])

    assert codigo == 0
    assert (salida / "VID_20261029_143010_anotado.mp4").stat().st_size > 0
    assert len(list((salida / "recortes").glob("*.jpg"))) == 1
    assert (salida / "mapa.html").exists()
    df = pd.read_csv(salida / "danos.csv")
    assert set(df.columns) == COLUMNAS_CSV
    assert len(df) == 1 and df.loc[0, "clase"] == "D40"
    assert df.loc[0, "latitud"] == pytest.approx(8.751, abs=0.0005)
    assert df.loc[0, "area_m2"] > 0

    bd = salida / "danos.db"
    assert main(["exportar", "--db", str(bd), "--csv", str(tmp_path / "copia.csv")]) == 0
    assert main(["mapa", "--db", str(bd)]) == 0
    assert main(["resumen", "--db", str(bd)]) == 0

    with BaseDatos(bd) as base:
        filas = base.danos()
    verdad = pd.read_csv(datos_prueba["verdad"]).to_dict("records")
    metricas = evaluar_campo(filas, verdad)
    assert (metricas.encontrados, metricas.verdad_total) == (1, 2)


def test_procesar_sin_video_falla_con_codigo_1(tmp_path):
    assert main(["procesar", "--video", str(tmp_path / "no_existe.mp4")]) == 1
