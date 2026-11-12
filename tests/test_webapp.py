"""Pruebas de la interfaz web.

Se saltan si Flask no está instalado (la CI instala solo `.[dev]`), así que no
afectan al resto de la suite. No dependen de YOLO, GPU ni red.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("flask")

from tapahuecos.clases import clase_por_codigo  # noqa: E402
from tapahuecos.registro import BaseDatos, Observacion  # noqa: E402
from tapahuecos.web import create_app  # noqa: E402
from tapahuecos.web.acciones import ACCIONES, por_id  # noqa: E402
from tapahuecos.web.ejecutor import Ejecutor  # noqa: E402


def _bd_con_un_dano(raiz: Path) -> int:
    """Crea salidas/Prueba/danos.db con un daño D40 y su recorte. Devuelve el id."""
    carpeta = raiz / "salidas" / "Prueba"
    (carpeta / "recortes").mkdir(parents=True)
    (carpeta / "recortes" / "001_00001_D40.jpg").write_bytes(b"jpeg-falso")
    with BaseDatos(carpeta / "danos.db") as bd:
        recorrido = bd.nuevo_recorrido("datos/videos/v.mp4", None, "modelos/best_rdd.pt")
        observacion = Observacion(
            track_id=1,
            clase=clase_por_codigo("D40"),
            confianza=0.62,
            fotograma=10,
            tiempo_video_s=0.2,
            instante_utc=None,
            latitud=None,
            longitud=None,
            area_px=120,
            area_m2=None,
            caja=(0, 0, 10, 10),
            recorte=np.zeros((8, 8, 3), dtype=np.uint8),
        )
        return bd.insertar_dano(recorrido, observacion, 3, "recortes/001_00001_D40.jpg")


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path)


# --------------------------------------------------------------------------- acciones


def test_catalogo_tiene_ids_unicos():
    ids = [a.id for a in ACCIONES]
    assert len(ids) == len(set(ids))
    assert "procesar" in ids and "verificar" in ids and "entrenar" in ids


def test_argv_traduce_el_formulario():
    accion = por_id("mapa")
    argv = accion.argv({"db": "salidas/danos.db", "recorrido": "2", "salida": "", "todos": "1"})
    assert argv == ["-m", "tapahuecos", "mapa", "--db", "salidas/danos.db", "--recorrido", "2", "--todos"]


def test_argv_de_lista_separa_valores():
    argv = por_id("preparar-rdd2022").argv(
        {"origen": "datos/RDD2022", "destino": "datos/rdd_yolo", "paises": "Japan, India Czech"}
    )
    assert argv[-4:] == ["--paises", "Japan", "India", "Czech"]


def test_argv_ignora_casillas_apagadas():
    argv = por_id("fusionar").argv({"db": "salidas/danos.db", "radio": "8", "cualquier-clase": ""})
    assert "--cualquier-clase" not in argv
    assert argv == ["-m", "tapahuecos", "fusionar", "--db", "salidas/danos.db", "--radio", "8"]


# ---------------------------------------------------------------------------- páginas


def test_indice_lista_las_acciones(app):
    respuesta = app.test_client().get("/")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert "Procesar un recorrido" in cuerpo
    assert "Revisar daños" not in cuerpo  # revisar es una página, no una acción del catálogo


def test_formulario_de_accion(app):
    respuesta = app.test_client().get("/accion/procesar")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert 'name="video"' in cuerpo
    assert "Ejecutar" in cuerpo


def test_accion_inexistente_da_404(app):
    assert app.test_client().get("/accion/no-existe").status_code == 404


def test_ejecutar_redirige_al_trabajo(app, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"video")
    registros: list = []

    class EjecutorFalso:
        def iniciar(self, accion, valores):
            registros.append((accion.id, valores))
            return SimpleNamespace(id="abc123")

        def obtener(self, _):
            return None

        def recientes(self, limite=6):
            return []

    app.config["EJECUTOR"] = EjecutorFalso()
    respuesta = app.test_client().post("/accion/verificar", data={"video": "v.mp4", "gpx": "", "pesos": ""})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/trabajo/abc123")
    assert registros == [("verificar", {"video": "v.mp4", "gpx": "", "pesos": ""})]


def test_procesar_sin_video_ni_camara_avisa(app):
    respuesta = app.test_client().post("/accion/procesar", data={"video": "", "camara": ""})
    assert respuesta.status_code == 400
    cuerpo = respuesta.get_data(as_text=True)
    assert "Indique" in cuerpo and "Video" in cuerpo


def test_procesar_acepta_camara(app):
    registros: list = []

    class EjecutorFalso:
        def iniciar(self, accion, valores):
            registros.append(valores)
            return SimpleNamespace(id="cam1")

        def obtener(self, _):
            return None

        def recientes(self, limite=6):
            return []

    app.config["EJECUTOR"] = EjecutorFalso()
    respuesta = app.test_client().post("/accion/procesar", data={"video": "", "camara": "0"})
    assert respuesta.status_code == 302
    assert registros[0]["camara"] == "0"


def test_validacion_avisa_de_ruta_inexistente(app):
    respuesta = app.test_client().post("/accion/verificar", data={"video": "no/existe.mp4"})
    assert respuesta.status_code == 400
    assert "No existe" in respuesta.get_data(as_text=True)


def test_evaluar_area_exige_medidos(app):
    respuesta = app.test_client().post("/accion/evaluar-area", data={"db": "", "medidos": ""})
    assert respuesta.status_code == 400
    assert "Huecos medidos" in respuesta.get_data(as_text=True)


def test_formulario_rellena_el_video_que_existe(app, tmp_path):
    (tmp_path / "datos" / "videos").mkdir(parents=True)
    (tmp_path / "datos" / "videos" / "VID_20261108_110401.mp4").write_bytes(b"video")
    cuerpo = app.test_client().get("/accion/procesar").get_data(as_text=True)
    assert 'value="datos/videos/VID_20261108_110401.mp4"' in cuerpo


def test_formulario_muestra_ejemplo_aparte_del_valor(app):
    cuerpo = app.test_client().get("/accion/procesar").get_data(as_text=True)
    # El ejemplo se muestra como ayuda, nunca como valor del campo.
    assert "Ejemplo:" in cuerpo
    assert 'value="0,0.45,1,1"' not in cuerpo


def test_vista_previa_del_comando(app):
    respuesta = app.test_client().post(
        "/api/comando/procesar",
        json={"video": "datos/videos/a.mp4", "region": "0,0.45,1,1", "todos": ""},
    )
    assert respuesta.status_code == 200
    comando = respuesta.get_json()["comando"]
    assert comando.startswith("python -m tapahuecos procesar")
    assert "--video datos/videos/a.mp4" in comando
    assert "--region 0,0.45,1,1" in comando
    assert "--todos" not in comando


def test_api_gpx_busca_el_que_coincide(app, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    import tapahuecos.web as web

    (tmp_path / "datos" / "gpx").mkdir(parents=True)
    inicio = datetime(2026, 11, 8, 16, 3, 58, tzinfo=timezone.utc)

    def escribir(nombre: str, desde_s: int, hasta_s: int) -> None:
        cuerpo = "".join(
            f'<trkpt lat="8.76{i}" lon="-75.87{i}"><time>'
            f"{(inicio + timedelta(seconds=desde_s + i)).isoformat().replace('+00:00', 'Z')}"
            "</time></trkpt>"
            for i in range(hasta_s - desde_s)
        )
        (tmp_path / "datos" / "gpx" / nombre).write_text(
            '<?xml version="1.0"?><gpx><trk><trkseg>' + cuerpo + "</trkseg></trk></gpx>",
            encoding="utf-8",
        )

    escribir("20261108-110219.gpx", 0, 20)
    escribir("20261108-110358.gpx", 200, 240)

    # El video empieza a las 16:04:00 y dura 10 s: coincide con el segundo GPX.
    monkeypatch.setattr(
        web, "_duracion_video", lambda *_: (inicio + timedelta(seconds=202), 10.0)
    )
    respuesta = app.test_client().get("/api/gpx?video=datos/videos/x.mp4")
    assert respuesta.get_json()["gpx"] == "datos/gpx/20261108-110358.gpx"


def test_trabajo_inexistente_da_404(app):
    assert app.test_client().get("/trabajo/zzz").status_code == 404


# ---------------------------------------------------------------------------- revisar


def test_revisar_lista_y_marca(app, tmp_path):
    dano_id = _bd_con_un_dano(tmp_path)
    cliente = app.test_client()

    pagina = cliente.get("/revisar?db=salidas/Prueba/danos.db")
    assert pagina.status_code == 200
    assert "D40" in pagina.get_data(as_text=True)

    marcado = cliente.post(
        "/api/revisar", json={"db": "salidas/Prueba/danos.db", "id": dano_id, "real": True}
    )
    assert marcado.status_code == 200
    datos = marcado.get_json()
    assert datos["ok"] is True
    assert datos["reales"] == 1
    assert datos["pendientes"] == 0

    with BaseDatos(tmp_path / "salidas" / "Prueba" / "danos.db") as bd:
        assert bd.danos()[0]["verificado"] == 1


def test_revisar_sin_base_de_datos_avisa(app, tmp_path):
    respuesta = app.test_client().get("/revisar?db=salidas/no-existe/danos.db")
    assert respuesta.status_code == 200
    assert "No existe la base de datos" in respuesta.get_data(as_text=True)


def test_revisar_rechaza_id_invalido(app, tmp_path):
    _bd_con_un_dano(tmp_path)
    respuesta = app.test_client().post("/api/revisar", json={"db": "salidas/Prueba/danos.db"})
    assert respuesta.status_code == 400


# ---------------------------------------------------------------------------- archivos


def test_salidas_lista_carpetas(app, tmp_path):
    _bd_con_un_dano(tmp_path)
    respuesta = app.test_client().get("/salidas")
    assert respuesta.status_code == 200
    assert "Prueba" in respuesta.get_data(as_text=True)


def test_archivo_sirve_un_recorte(app, tmp_path):
    _bd_con_un_dano(tmp_path)
    ruta = "/archivo/salidas/Prueba/recortes/001_00001_D40.jpg"
    assert app.test_client().get(ruta).status_code == 200


def test_archivo_bloquea_salir_de_la_raiz(app, tmp_path):
    secreto = tmp_path.parent / "secreto.txt"
    secreto.write_text("no se debe servir", encoding="utf-8")
    # %2e%2e evita que el cliente normalice el ".." antes de enrutar.
    respuesta = app.test_client().get("/archivo/%2e%2e/secreto.txt")
    assert respuesta.status_code == 404


def test_archivo_inexistente_da_404(app):
    assert app.test_client().get("/archivo/salidas/nada.jpg").status_code == 404


# ---------------------------------------------------------------------------- ejecutor


def test_ejecutor_captura_salida_y_codigo(tmp_path):
    accion = SimpleNamespace(id="eco", nombre="Eco", argv=lambda _v: ["-c", "print('hola mundo')"])
    ejecutor = Ejecutor(tmp_path)
    trabajo = ejecutor.iniciar(accion, {})

    limite = time.time() + 20
    while trabajo.estado == "en_curso" and time.time() < limite:
        time.sleep(0.05)

    assert trabajo.estado == "terminado"
    assert trabajo.codigo == 0
    assert any("hola mundo" in linea for linea in trabajo.desde(0))


def test_ejecutor_marca_error(tmp_path):
    accion = SimpleNamespace(id="falla", nombre="Falla", argv=lambda _v: ["-c", "raise SystemExit(3)"])
    ejecutor = Ejecutor(tmp_path)
    trabajo = ejecutor.iniciar(accion, {})

    limite = time.time() + 20
    while trabajo.estado == "en_curso" and time.time() < limite:
        time.sleep(0.05)

    assert trabajo.estado == "error"
    assert trabajo.codigo == 3
