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


def test_max_fotogramas_en_la_consola(
    tmp_path, datos_prueba, config_yaml, monkeypatch, capsys, caplog
):
    monkeypatch.setattr(tapahuecos.detector, "Detector", DetectorSimulado)

    codigo = main([
        "procesar", "--video", str(datos_prueba["video"]), "--gpx", str(datos_prueba["gpx"]),
        "--config", str(config_yaml), "--salida", str(tmp_path / "salidas"),
        "--max-fotogramas", "1",
    ])

    assert codigo == 0
    assert "1 fotogramas" in capsys.readouterr().out
    assert main([
        "procesar", "--video", str(datos_prueba["video"]), "--config", str(config_yaml),
        "--salida", str(tmp_path / "otra"), "--max-fotogramas", "0",
    ]) == 1
    assert "--max-fotogramas debe ser" in caplog.text


# --- Ayuda y mensajes de error (issue #21): en español, sin traza de Python ---


def test_ayuda_en_espanol(capsys):
    with pytest.raises(SystemExit) as salida:
        main(["procesar", "--help"])
    assert salida.value.code == 0
    texto = capsys.readouterr().out
    assert texto.startswith("uso: tapahuecos procesar")
    assert "muestra esta ayuda" in texto
    assert "modelos/best_rdd.pt" in texto


def test_opcion_faltante_explica_en_espanol(capsys):
    with pytest.raises(SystemExit) as salida:
        main(["procesar"])
    assert salida.value.code == 2
    error = capsys.readouterr().err
    assert "falta una de estas opciones: --video --camara" in error
    assert "tapahuecos procesar --help" in error


def test_valor_no_numerico_explica_en_espanol(capsys):
    with pytest.raises(SystemExit):
        main(["resumen", "--recorrido", "abc"])
    assert "--recorrido: valor no válido: 'abc' (debe ser un número)" in capsys.readouterr().err


def test_gpx_danado_no_muestra_traza(tmp_path, datos_prueba, config_yaml, caplog):
    gpx = tmp_path / "roto.gpx"
    gpx.write_text("<gpx><trk> sin cerrar", encoding="utf-8")
    codigo = main([
        "procesar", "--video", str(datos_prueba["video"]), "--gpx", str(gpx),
        "--config", str(config_yaml), "--salida", str(tmp_path / "salidas"),
    ])
    assert codigo == 1
    assert "No se pudo leer el GPX" in caplog.text


def test_bd_que_no_es_sqlite_no_muestra_traza(tmp_path, caplog):
    bd = tmp_path / "danos.db"
    bd.write_text("esto no es sqlite", encoding="utf-8")
    assert main(["resumen", "--db", str(bd)]) == 1
    assert "como base de datos de TapaHuecos" in caplog.text


def test_bd_inexistente_dice_que_hacer(tmp_path):
    with pytest.raises(SystemExit) as salida:
        main(["resumen", "--db", str(tmp_path / "no_existe.db")])
    assert "tapahuecos procesar" in str(salida.value.code)
    assert "--db" in str(salida.value.code)


def test_config_inexistente_en_espanol(tmp_path, datos_prueba, caplog):
    codigo = main([
        "procesar", "--video", str(datos_prueba["video"]),
        "--config", str(tmp_path / "no_existe.yaml"),
    ])
    assert codigo == 1
    assert "No existe el archivo" in caplog.text
    assert "No such file" not in caplog.text


@pytest.mark.parametrize(
    "opcion, valor", [("--inicio", "ayer"), ("--region", "1,2"), ("--cada", "0")]
)
def test_inicio_y_region_invalidos_explican_el_formato(tmp_path, datos_prueba, caplog, opcion, valor):
    codigo = main(["procesar", "--video", str(datos_prueba["video"]), opcion, valor])
    assert codigo == 1
    assert f"{opcion} debe ser" in caplog.text


def test_camara_inexistente_da_pista(tmp_path, config_yaml, monkeypatch, caplog):
    monkeypatch.setattr(tapahuecos.detector, "Detector", DetectorSimulado)
    codigo = main([
        "procesar", "--camara", "99", "--config", str(config_yaml),
        "--salida", str(tmp_path / "salidas"),
    ])
    assert codigo == 1
    assert "Revise que la cámara 99 esté conectada" in caplog.text
