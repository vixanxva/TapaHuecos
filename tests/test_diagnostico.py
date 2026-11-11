"""Pruebas de `tapahuecos verificar` (diagnóstico sin cargar YOLO)."""

import gpxpy
import pytest

import tapahuecos.diagnostico as diagnostico
from tapahuecos.cli import main
from tapahuecos.config import Config


@pytest.fixture
def cfg(tmp_path):
    cfg = Config()
    cfg.modelo.pesos = str(tmp_path / "best.pt")
    (tmp_path / "best.pt").write_bytes(b"pesos de prueba")
    cfg.calibracion.homografia = None
    cfg.calibracion.metros_por_pixel = 0.005
    return cfg


@pytest.fixture
def sin_yolo(monkeypatch):
    monkeypatch.setattr(
        diagnostico, "_comprobar_yolo",
        lambda: diagnostico.Comprobacion("Ultralytics", "ok", "instalado 8.3"),
    )
    monkeypatch.setattr(
        diagnostico, "_comprobar_torch",
        lambda: diagnostico.Comprobacion("PyTorch", "ok", "2.6; CPU"),
    )


def test_entorno_listo(cfg, sin_yolo):
    comprobaciones = diagnostico.comprobar_entorno(cfg)
    assert not [c for c in comprobaciones if c.estado == "error"]
    assert {c.nombre for c in comprobaciones} >= {"Python", "Modelo", "Calibración"}


def test_yolo_faltante_explica_como_instalarlo(monkeypatch):
    monkeypatch.setattr(diagnostico, "_instalado", lambda nombre: False)
    comprobacion = diagnostico._comprobar_yolo()
    assert comprobacion.estado == "error"
    assert 'pip install -e ".[yolo]"' in comprobacion.detalle


def test_modelo_faltante_es_error(tmp_path, sin_yolo):
    cfg = Config()
    cfg.modelo.pesos = str(tmp_path / "no_existe.pt")
    cfg.calibracion.homografia = None
    cfg.calibracion.metros_por_pixel = 0.005

    comprobaciones = diagnostico.comprobar_entorno(cfg)
    modelo = next(c for c in comprobaciones if c.nombre == "Modelo")
    assert modelo.estado == "error"
    assert "no existe" in modelo.detalle


def test_video_y_gpx_sin_solape_avisan(tmp_path, cfg, sin_yolo, datos_prueba):
    ruta_gpx = tmp_path / "otro_momento.gpx"
    gpx = gpxpy.parse(datos_prueba["gpx"].read_text(encoding="utf-8"))
    for pista in gpx.tracks:
        for segmento in pista.segments:
            for punto in segmento.points:
                punto.time = punto.time.replace(hour=(punto.time.hour + 2) % 24)
    ruta_gpx.write_text(gpx.to_xml(), encoding="utf-8")

    comprobaciones = diagnostico.comprobar_entorno(
        cfg, None, datos_prueba["video"], ruta_gpx
    )
    solape = next(c for c in comprobaciones if c.nombre == "Solape video/GPX")
    assert solape.estado == "aviso"
    assert "sin coordenadas" in solape.detalle


def test_verificar_en_consola(tmp_path, sin_yolo, capsys):
    config = tmp_path / "config.yaml"
    pesos = tmp_path / "best.pt"
    pesos.write_bytes(b"pesos de prueba")
    config.write_text(
        "modelo:\n"
        f"  pesos: {pesos}\n"
        "calibracion:\n"
        "  homografia: null\n"
        "  metros_por_pixel: 0.005\n",
        encoding="utf-8",
    )

    assert main(["verificar", "--config", str(config)]) == 0
    texto = capsys.readouterr().out
    assert "[OK]     Modelo:" in texto
    assert "Todo listo" in texto


def test_verificar_falla_si_falta_el_modelo(tmp_path, sin_yolo, capsys):
    config = tmp_path / "config.yaml"
    config.write_text(
        "modelo:\n"
        f"  pesos: {tmp_path / 'no_existe.pt'}\n"
        "calibracion:\n"
        "  homografia: null\n"
        "  metros_por_pixel: 0.005\n",
        encoding="utf-8",
    )

    assert main(["verificar", "--config", str(config)]) == 1
    texto = capsys.readouterr().out
    assert "[ERROR]  Modelo:" in texto
    assert "Corrija los errores" in texto
