import numpy as np

from tapahuecos.clases import clase_por_codigo
from tapahuecos.evaluacion import evaluar_campo
from tapahuecos.registro import BaseDatos, GestorDanos, Observacion


def _obs(track_id, fotograma, confianza=0.5, lat=8.75):
    return Observacion(
        track_id=track_id, clase=clase_por_codigo("D40"), confianza=confianza,
        fotograma=fotograma, tiempo_video_s=fotograma / 30, instante_utc=None,
        latitud=lat, longitud=-75.88, area_px=100, area_m2=0.1, caja=(0, 0, 10, 10),
        recorte=np.zeros((10, 10, 3), np.uint8),
    )


def test_un_registro_por_dano_y_filtro_de_espurios(tmp_path):
    with BaseDatos(tmp_path / "danos.db") as bd:
        rid = bd.nuevo_recorrido("v.mp4", None, "best.pt")
        gestor = GestorDanos(bd, rid, tmp_path / "recortes", min_fotogramas=3, max_ausencia=10)
        for f, conf in enumerate([0.4, 0.9, 0.6, 0.5]):
            gestor.observar(_obs(1, f, conf))
        gestor.observar(_obs(2, 0))  # visto una sola vez: se descarta

        gestor.cerrar_ausentes(50)
        gestor.observar(_obs(1, 51, 0.99))  # reaparece tras cerrarse: no se duplica
        assert gestor.finalizar() == 1

        filas = bd.danos()
        assert len(filas) == 1
        assert filas[0]["track_id"] == 1
        assert filas[0]["confianza"] == 0.9
        assert filas[0]["veces_visto"] == 4
        assert (tmp_path / filas[0]["recorte"]).exists()


def test_metricas_de_campo(tmp_path):
    with BaseDatos(tmp_path / "danos.db") as bd:
        rid = bd.nuevo_recorrido("v.mp4", None, "best.pt")
        gestor = GestorDanos(bd, rid, tmp_path / "recortes", min_fotogramas=1)
        gestor.observar(_obs(1, 0, lat=8.7500))
        gestor.observar(_obs(2, 0, lat=8.7600))
        gestor.finalizar()
        ids = [f["id"] for f in bd.danos()]
        bd.marcar(ids[0], True)
        bd.marcar(ids[1], False)
        filas = bd.danos()

    verdad = [{"latitud": 8.75003, "longitud": -75.88}, {"latitud": 8.80, "longitud": -75.88}]
    m = evaluar_campo(filas, verdad, radio_m=10)
    assert m.precision == 0.5
    assert m.exhaustividad == 0.5
    assert m.f1 == 0.5
