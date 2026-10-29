import pytest

from tapahuecos.evaluacion import emparejar_huecos, evaluar_area

LAT, LON = 8.75, -75.88
PASO = 0.00001  # grados de latitud, ≈ 1.11 m


def _fila(id_, metros, area=0.5, verificado=None, clase="D40", lat=LAT):
    """Registro de la base de datos a `metros` (en pasos de ≈ 1.11 m) al norte del origen."""
    return {"id": id_, "clase": clase, "latitud": None if lat is None else lat + metros * PASO,
            "longitud": LON, "area_m2": area, "verificado": verificado}


def _hueco(metros, area=0.5):
    return {"latitud": LAT + metros * PASO, "longitud": LON, "area_m2": area}


def test_emparejamiento_uno_a_uno():
    # Los dos huecos tienen más cerca el registro 1; el primero lo gana y el segundo
    # se queda con el registro 2, aunque esté más lejos.
    filas = [_fila(1, 0), _fila(2, 5)]
    medidos = [_hueco(1), _hueco(2)]
    pares = emparejar_huecos(filas, medidos, radio_m=10)
    assert [(p.medido, p.registro_id) for p in pares] == [(0, 1), (1, 2)]
    assert pares[0].distancia_m == pytest.approx(1.11, abs=0.01)
    assert pares[1].distancia_m == pytest.approx(3.34, abs=0.01)


def test_respeta_el_radio():
    filas = [_fila(1, 0), _fila(2, 20)]  # el registro 2 queda a ≈ 11 m del segundo hueco
    medidos = [_hueco(0), _hueco(10)]
    pares = emparejar_huecos(filas, medidos, radio_m=10)
    assert [(p.medido, p.registro_id) for p in pares] == [(0, 1)]
    assert len(emparejar_huecos(filas, medidos, radio_m=12)) == 2


def test_excluye_falsos_positivos_sin_coordenada_y_otras_clases():
    filas = [
        _fila(1, 0, verificado=0),  # marcado como falso
        _fila(2, 0, lat=None),  # sin coordenada
        _fila(3, 0, clase="D00"),  # grieta, no hueco
        _fila(4, 3, verificado=1),
    ]
    pares = emparejar_huecos(filas, [_hueco(0)], radio_m=10)
    assert [p.registro_id for p in pares] == [4]


def test_errores_con_valores_conocidos():
    filas = [_fila(1, 0, area=1.2), _fila(2, 100, area=0.5), _fila(3, 200, area=0.3)]
    medidos = [_hueco(0, area=1.0), _hueco(102, area=0.4), _hueco(206, area=0.6)]
    e = evaluar_area(filas, medidos, radio_m=10)
    assert (e.n_medidos, e.n_emparejados) == (3, 3)
    # Errores de área: 0.2/1.0 = 20 %, 0.1/0.4 = 25 %, 0.3/0.6 = 50 %.
    assert [p.error_area for p in e.pares] == pytest.approx([0.20, 0.25, 0.50])
    assert e.area_media == pytest.approx(0.95 / 3)
    assert e.area_mediana == pytest.approx(0.25)
    assert e.area_maximo == pytest.approx(0.50)
    # Errores de posición: 0, 2 y 6 pasos de ≈ 1.11 m.
    assert e.posicion_media_m == pytest.approx(8 / 3 * 1.112, rel=0.01)
    assert e.posicion_mediana_m == pytest.approx(2 * 1.112, rel=0.01)
    assert e.posicion_maximo_m == pytest.approx(6 * 1.112, rel=0.01)


def test_registro_sin_area():
    filas = [_fila(1, 0, area=None), _fila(2, 100, area=0.5)]
    medidos = [_hueco(0, area=1.0), _hueco(100, area=0.4)]
    e = evaluar_area(filas, medidos, radio_m=10)
    assert e.n_emparejados == 2
    assert e.pares[0].error_area is None  # la posición sí cuenta, el área no
    assert e.area_media == e.area_maximo == pytest.approx(0.25)
    assert e.posicion_maximo_m == pytest.approx(0.0)

    solo_sin_area = evaluar_area(filas[:1], medidos[:1], radio_m=10)
    assert solo_sin_area.n_emparejados == 1
    assert solo_sin_area.area_media is None
    assert solo_sin_area.area_mediana is None
    assert solo_sin_area.area_maximo is None
    assert solo_sin_area.posicion_media_m == pytest.approx(0.0)
