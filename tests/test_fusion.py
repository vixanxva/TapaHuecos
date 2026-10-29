import sqlite3

import numpy as np

from tapahuecos.clases import clase_por_codigo
from tapahuecos.fusion import agrupar, fusionar_bd, unicos
from tapahuecos.registro import BaseDatos, GestorDanos, Observacion

# 0.00001° de latitud ≈ 1.11 m
LAT, LON = 8.75, -75.88


def _fila(id_, recorrido, metros_norte=0.0, clase="D40", confianza=0.5, verificado=None):
    return {
        "id": id_, "recorrido_id": recorrido, "clase": clase, "confianza": confianza,
        "latitud": LAT + metros_norte / 111_195, "longitud": LON, "verificado": verificado,
        "grupo": None,
    }


def test_mismo_hueco_en_dos_recorridos_se_agrupa():
    grupos = agrupar([_fila(1, 1), _fila(2, 2, metros_norte=3), _fila(3, 3, metros_norte=50)])
    assert grupos[1] == grupos[2]
    assert grupos[3] != grupos[1]


def test_no_agrupa_dentro_del_mismo_recorrido():
    grupos = agrupar([_fila(1, 1), _fila(2, 1, metros_norte=3)])
    assert grupos[1] != grupos[2]


def test_no_agrupa_clases_distintas_salvo_que_se_pida():
    filas = [_fila(1, 1, clase="D40"), _fila(2, 2, clase="D00")]
    assert agrupar(filas)[1] != agrupar(filas)[2]
    sin_clase = agrupar(filas, misma_clase=False)
    assert sin_clase[1] == sin_clase[2]


def test_no_encadena_grupos():
    # A–B a 6 m y B–C a 6 m, pero A–C a 12 m: C no entra al grupo de A.
    filas = [
        _fila(1, 1, 0, confianza=0.9),
        _fila(2, 2, 6, confianza=0.5),
        _fila(3, 3, 12, confianza=0.4),
    ]
    grupos = agrupar(filas, radio_m=8)
    assert grupos[1] == grupos[2]
    assert grupos[3] == 3


def test_sin_coordenada_es_su_propio_grupo():
    fila = _fila(1, 1)
    fila["latitud"] = None
    assert agrupar([fila]) == {1: 1}


def test_unicos_prefiere_el_confirmado_como_real():
    filas = [
        {**_fila(1, 1, confianza=0.95), "grupo": 1},
        {**_fila(2, 2, confianza=0.60, verificado=1), "grupo": 1},
        {**_fila(3, 3, metros_norte=50), "grupo": 3},
    ]
    resultado = unicos(filas)
    assert [f["id"] for f in resultado] == [2, 3]
    assert resultado[0]["registros"] == 2


def _obs(track_id, metros_norte):
    return Observacion(
        track_id=track_id, clase=clase_por_codigo("D40"), confianza=0.8, fotograma=0,
        tiempo_video_s=0.0, instante_utc=None, latitud=LAT + metros_norte / 111_195,
        longitud=LON, area_px=100, area_m2=0.1, caja=(0, 0, 10, 10),
        recorte=np.zeros((10, 10, 3), np.uint8),
    )


def test_fusionar_bd(tmp_path):
    with BaseDatos(tmp_path / "danos.db") as bd:
        for metros in (0, 2):  # el mismo hueco, en dos recorridos
            rid = bd.nuevo_recorrido("v.mp4", None, "best.pt")
            gestor = GestorDanos(bd, rid, tmp_path / "recortes", min_fotogramas=1)
            gestor.observar(_obs(1, metros))
            gestor.finalizar()
        assert fusionar_bd(bd, radio_m=8) == (2, 1)
        assert len({f["grupo"] for f in bd.danos()}) == 1


def test_migra_bases_de_datos_sin_columna_grupo(tmp_path):
    ruta = tmp_path / "vieja.db"
    with sqlite3.connect(ruta) as con:
        con.execute("CREATE TABLE danos (id INTEGER PRIMARY KEY, clase TEXT)")
    with BaseDatos(ruta) as bd:
        columnas = {fila["name"] for fila in bd.con.execute("PRAGMA table_info(danos)")}
    assert "grupo" in columnas
