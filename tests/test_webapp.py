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


def test_revisar_rechaza_bd_fuera_del_proyecto(app, tmp_path):
    ajena = tmp_path.parent / "ajena.db"
    ajena.write_bytes(b"")
    respuesta = app.test_client().get(f"/revisar?db={ajena.as_posix()}")
    assert respuesta.status_code == 200
    assert "No existe la base de datos" in respuesta.get_data(as_text=True)
    assert ajena.read_bytes() == b""  # no se le crearon tablas

    marcar = app.test_client().post("/api/revisar", json={"db": "../ajena.db", "id": 1, "real": True})
    assert marcar.status_code == 404


def test_revisar_avisa_si_el_archivo_no_es_sqlite(app, tmp_path):
    (tmp_path / "config.yaml").write_text("modelo: {}\n", encoding="utf-8")
    respuesta = app.test_client().get("/revisar?db=config.yaml")
    assert respuesta.status_code == 200
    assert "no es una base de datos" in respuesta.get_data(as_text=True)


# ------------------------------------------------------------------------- seguridad


def _ejecutor_que_registra(registros: list):
    return SimpleNamespace(
        iniciar=lambda accion, valores: registros.append(accion.id) or SimpleNamespace(id="x1"),
        obtener=lambda _id: None,
        recientes=lambda limite=6: [],
    )


def test_post_desde_otra_pagina_se_rechaza(app):
    registros: list = []
    app.config["EJECUTOR"] = _ejecutor_que_registra(registros)
    respuesta = app.test_client().post(
        "/accion/exportar",
        data={"db": "", "csv": "C:/Users/otro/Documents/tesis.docx"},
        headers={"Origin": "https://malo.example"},
    )
    assert respuesta.status_code == 403
    assert registros == []


def test_post_con_referer_ajeno_se_rechaza(app):
    respuesta = app.test_client().post(
        "/api/revisar", json={"id": 1, "real": True},
        headers={"Referer": "http://malo.example/pagina"},
    )
    assert respuesta.status_code == 403


def test_post_desde_la_propia_interfaz_se_acepta(app, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"video")
    registros: list = []
    app.config["EJECUTOR"] = _ejecutor_que_registra(registros)
    respuesta = app.test_client().post(
        "/accion/verificar", data={"video": "v.mp4"}, headers={"Origin": "http://localhost"}
    )
    assert respuesta.status_code == 302
    assert registros == ["verificar"]


def test_host_ajeno_se_rechaza(app):
    # DNS rebinding: un dominio externo que apunta a 127.0.0.1 llega con su propio Host.
    assert app.test_client().get("/", headers={"Host": "malo.example:5000"}).status_code == 403
    assert app.test_client().get("/", headers={"Host": "127.0.0.1:5000"}).status_code == 200


def test_host_ajeno_se_acepta_si_se_desactiva_la_comprobacion(app):
    app.config["HOSTS_PERMITIDOS"] = None
    assert app.test_client().get("/", headers={"Host": "192.168.1.20:5000"}).status_code == 200


def test_procesar_con_video_y_camara_avisa(app, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"video")
    respuesta = app.test_client().post("/accion/procesar", data={"video": "v.mp4", "camara": "0"})
    assert respuesta.status_code == 400
    assert "Indique solo uno" in respuesta.get_data(as_text=True)


def test_lista_no_admite_opciones_inyectadas(app):
    respuesta = app.test_client().post(
        "/accion/preparar-rdd2022",
        data={"origen": "", "destino": "datos/rdd_yolo", "paises": "Japan --vacias 0.9"},
    )
    assert respuesta.status_code == 400
    assert "no puede contener opciones" in respuesta.get_data(as_text=True)


def test_acciones_de_la_cli_coinciden_con_el_parser():
    """Cada acción de `python -m tapahuecos` debe ser aceptada por el parser real."""
    from tapahuecos.cli import construir_parser

    ejemplo = {"texto": "x", "numero": "1", "casilla": "1", "lista": "a"}
    for accion in ACCIONES:
        if accion.comando[:2] != ("-m", "tapahuecos"):
            continue
        omitidos = set(accion.requiere_uno_de[1:])  # solo uno de los excluyentes
        valores = {c.nombre: ejemplo[c.tipo] for c in accion.campos if c.nombre not in omitidos}
        if "region" in valores:
            valores["region"] = "0,0.45,1,1"
        if "inicio" in valores:
            valores["inicio"] = "2026-11-08T11:04:01"
        construir_parser().parse_args(accion.argv(valores)[2:])  # SystemExit si no coincide


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


def test_trabajo_sigue_entregando_lineas_despues_del_tope(monkeypatch):
    import tapahuecos.web.ejecutor as ejecutor_mod

    monkeypatch.setattr(ejecutor_mod, "MAX_LINEAS", 5)
    accion = SimpleNamespace(id="eco", nombre="Eco")
    trabajo = ejecutor_mod.Trabajo(accion, ["-c", "pass"])
    for i in range(8):
        trabajo.agregar(f"linea {i}")

    lineas, total = trabajo.leer(0)
    assert total == 8
    assert lineas == [f"linea {i}" for i in range(3, 8)]  # solo se conservan las últimas 5

    trabajo.agregar("linea 8")
    nuevas, total = trabajo.leer(8)
    assert nuevas == ["linea 8"] and total == 9  # antes quedaba congelado en el tope
    assert trabajo.instantanea()["total"] == 9


def test_api_trabajo_devuelve_total_absoluto(app, monkeypatch):
    import tapahuecos.web.ejecutor as ejecutor_mod

    monkeypatch.setattr(ejecutor_mod, "MAX_LINEAS", 3)
    trabajo = ejecutor_mod.Trabajo(SimpleNamespace(id="eco", nombre="Eco"), ["-c", "pass"])
    for i in range(6):
        trabajo.agregar(str(i))
    app.config["EJECUTOR"] = SimpleNamespace(obtener=lambda _id: trabajo)

    datos = app.test_client().get(f"/api/trabajo/{trabajo.id}?desde=4").get_json()
    assert datos["lineas"] == ["4", "5"]
    assert datos["total"] == 6


def _esperar(trabajo, segundos: float = 20) -> None:
    limite = time.time() + segundos
    while trabajo.estado == "en_curso" and time.time() < limite:
        time.sleep(0.05)


_CODIGO_LENTO = "import time; print('empiezo', flush=True); time.sleep(60)"


def _accion_lenta(accion_id: str = "lenta"):
    return SimpleNamespace(id=accion_id, nombre="Lenta", argv=lambda _v: ["-c", _CODIGO_LENTO])


def test_ejecutor_cancela_un_trabajo(tmp_path):
    ejecutor = Ejecutor(tmp_path)
    trabajo = ejecutor.iniciar(_accion_lenta(), {})
    limite = time.time() + 20
    while not trabajo.desde(0) and time.time() < limite:  # que el proceso haya arrancado
        time.sleep(0.05)

    assert ejecutor.cancelar(trabajo.id) is True
    _esperar(trabajo)
    assert trabajo.estado == "cancelado"
    assert time.time() - trabajo.inicio < 30  # no esperó los 60 s del sleep
    assert ejecutor.cancelar(trabajo.id) is False  # ya terminó


def test_ejecutor_no_lanza_dos_veces_la_misma_accion(tmp_path):
    from tapahuecos.web.ejecutor import TrabajoEnCurso

    ejecutor = Ejecutor(tmp_path)
    primero = ejecutor.iniciar(_accion_lenta(), {})
    try:
        with pytest.raises(TrabajoEnCurso) as error:
            ejecutor.iniciar(_accion_lenta(), {})
        assert error.value.trabajo is primero
        otra = ejecutor.iniciar(_accion_lenta("otra"), {})  # otra acción sí puede correr
        ejecutor.cancelar(otra.id)
    finally:
        ejecutor.cancelar(primero.id)
        _esperar(primero)


def test_ejecutor_no_olvida_trabajos_en_curso(tmp_path):
    ejecutor = Ejecutor(tmp_path, max_trabajos=2)
    lento = ejecutor.iniciar(_accion_lenta(), {})
    try:
        for i in range(3):
            rapido = ejecutor.iniciar(
                SimpleNamespace(id=f"r{i}", nombre="R", argv=lambda _v: ["-c", "pass"]), {}
            )
            _esperar(rapido)
        assert ejecutor.obtener(lento.id) is lento
    finally:
        ejecutor.cancelar(lento.id)
        _esperar(lento)


def test_formulario_avisa_si_la_accion_ya_corre(app, tmp_path):
    from tapahuecos.web.ejecutor import TrabajoEnCurso

    (tmp_path / "v.mp4").write_bytes(b"video")

    class EjecutorOcupado:
        def iniciar(self, accion, valores):
            raise TrabajoEnCurso(SimpleNamespace(id="viejo1", accion_nombre=accion.nombre))

    app.config["EJECUTOR"] = EjecutorOcupado()
    respuesta = app.test_client().post("/accion/verificar", data={"video": "v.mp4"})
    assert respuesta.status_code == 409
    cuerpo = respuesta.get_data(as_text=True)
    assert "en curso" in cuerpo and "/trabajo/viejo1" in cuerpo


def test_api_cancelar(app):
    estados = {"t1": True, "t2": False}
    app.config["EJECUTOR"] = SimpleNamespace(
        obtener=lambda i: i if i in estados else None,
        cancelar=lambda i: estados[i],
    )
    cliente = app.test_client()
    assert cliente.post("/api/trabajo/t1/cancelar").get_json() == {"ok": True}
    assert cliente.post("/api/trabajo/t2/cancelar").status_code == 409
    assert cliente.post("/api/trabajo/nada/cancelar").status_code == 404
    assert cliente.post("/api/trabajo/t1/cancelar",
                        headers={"Origin": "https://malo.example"}).status_code == 403


def test_lista_con_punto_y_coma_admite_rutas_con_espacios():
    from tapahuecos.web.acciones import partes_de_lista

    assert partes_de_lista("C:/Users/Juan Pérez/rdd_yolo; datos/monteria") == [
        "C:/Users/Juan Pérez/rdd_yolo", "datos/monteria"
    ]
    assert partes_de_lista("Japan, India Czech") == ["Japan", "India", "Czech"]


def test_vista_previa_pone_comillas_a_las_rutas_con_espacios():
    from tapahuecos.web.acciones import mostrar_comando

    texto = mostrar_comando(["python", "-m", "tapahuecos", "verificar", "--video", "mis videos/v.mp4"])
    assert '"mis videos/v.mp4"' in texto or "'mis videos/v.mp4'" in texto


def test_avisa_si_no_es_la_carpeta_del_proyecto(tmp_path):
    from tapahuecos.web import faltantes_del_proyecto

    assert faltantes_del_proyecto(tmp_path) == ["scripts/", "config.yaml"]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "config.yaml").write_text("", encoding="utf-8")
    assert faltantes_del_proyecto(tmp_path) == []


def test_ejecutor_marca_error(tmp_path):
    accion = SimpleNamespace(id="falla", nombre="Falla", argv=lambda _v: ["-c", "raise SystemExit(3)"])
    ejecutor = Ejecutor(tmp_path)
    trabajo = ejecutor.iniciar(accion, {})

    limite = time.time() + 20
    while trabajo.estado == "en_curso" and time.time() < limite:
        time.sleep(0.05)

    assert trabajo.estado == "error"
    assert trabajo.codigo == 3
