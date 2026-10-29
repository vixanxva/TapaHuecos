from datetime import timedelta

import pytest

from tapahuecos.gps import PuntoGPS, Recorrido, distancia_m


def test_interpola_entre_puntos(gpx_recto):
    ruta, inicio = gpx_recto
    recorrido = Recorrido.desde_gpx(ruta)
    lat, lon = recorrido.posicion(inicio + timedelta(seconds=10.5))
    assert lat == pytest.approx(8.75 + 10.5 * 0.0001)
    assert lon == pytest.approx(-75.88)


def test_fuera_del_recorrido_devuelve_none(gpx_recto):
    ruta, inicio = gpx_recto
    recorrido = Recorrido.desde_gpx(ruta)
    assert recorrido.posicion(inicio - timedelta(seconds=30)) is None
    assert recorrido.posicion(inicio + timedelta(seconds=63), tolerancia_s=5) is not None


def test_hueco_largo_en_el_gps(gpx_recto):
    ruta, inicio = gpx_recto
    puntos = [PuntoGPS(inicio, 8.0, -75.0), PuntoGPS(inicio + timedelta(seconds=120), 8.1, -75.0)]
    recorrido = Recorrido(puntos, max_hueco_s=30)
    assert recorrido.posicion(inicio + timedelta(seconds=60)) is None
    assert recorrido.posicion(inicio + timedelta(seconds=2)) == (8.0, -75.0)


def test_distancia_haversine():
    # 0.001° de latitud ≈ 111 m
    assert distancia_m(8.75, -75.88, 8.751, -75.88) == pytest.approx(111.2, abs=0.5)
