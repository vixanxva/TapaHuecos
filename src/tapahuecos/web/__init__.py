"""Interfaz web local para ejecutar el proyecto desde el navegador.

No duplica lógica: cada acción arma el mismo comando de consola (`python -m tapahuecos …`
o un script de `scripts/`) y muestra su salida en vivo. La única función que no puede
ser un comando es `revisar`, porque abre una ventana de OpenCV; aquí se reemplaza por
una galería que marca cada daño como real o falso directamente en la base de datos.

Uso:
    pip install -e ".[web]"
    tapahuecos-web            # o: python -m tapahuecos.web
y abrir http://127.0.0.1:5000
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from tapahuecos.config import Config, cargar_config
from tapahuecos.entrada import resolver_inicio
from tapahuecos.gps import Recorrido
from tapahuecos.registro import BaseDatos
from tapahuecos.web import acciones as cat
from tapahuecos.web.ejecutor import Ejecutor

BD_PREDETERMINADA = "salidas/danos.db"


# --------------------------------------------------------------------- insumos


def _config(raiz: Path) -> Config:
    """Configuración del proyecto; si no hay config.yaml (o está mal), usa las predeterminadas."""
    ruta = raiz / "config.yaml"
    try:
        return cargar_config(ruta if ruta.is_file() else None)
    except ValueError:
        return Config()


def _cuenta_danos(ruta: Path) -> int:
    """Número de daños de una base de datos, o -1 si no se puede leer."""
    try:
        with sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True) as con:
            return int(con.execute("SELECT COUNT(*) FROM danos").fetchone()[0])
    except (sqlite3.Error, OSError):
        return -1


def _sugerencias(raiz: Path) -> dict[str, list[str]]:
    """Rutas que ya existen, para ofrecerlas como opciones en los formularios."""

    def buscar(patron: str) -> list[Path]:
        return [p for p in raiz.glob(patron) if p.is_file()]

    def relativas(patron: str) -> list[str]:
        return sorted(p.relative_to(raiz).as_posix() for p in buscar(patron))

    def carpetas(*candidatas: str) -> list[str]:
        return [c for c in candidatas if (raiz / c).is_dir()]

    # La base de datos con más daños primero: suele ser la de la campaña real, no una
    # corrida de prueba. En empate, la más reciente.
    bases = sorted(buscar("salidas/**/danos.db") + buscar("danos.db"),
                   key=lambda p: (_cuenta_danos(p), p.stat().st_mtime), reverse=True)
    return {
        "video": relativas("datos/videos/*.mp4") + relativas("datos/demo/*.mp4"),
        "gpx": relativas("datos/gpx/*.gpx") + relativas("datos/demo/*.gpx"),
        "db": [p.relative_to(raiz).as_posix() for p in bases],
        "pesos": relativas("modelos/*.pt"),
        "csv": relativas("datos/*.csv"),
        "imagenes": carpetas(
            "datos/rdd_yolo/images/test", "datos/rdd_yolo/images/val", "datos/rdd_yolo/images/train"
        ),
        "salida": sorted(p.relative_to(raiz).as_posix() for p in raiz.glob("salidas/*") if p.is_dir()),
    }


def _duracion_video(raiz: Path, video_rel: str, cfg: Config):
    """Hora de inicio y duración del video, o (None, None) si no se puede leer."""
    import cv2

    ruta = raiz / video_rel
    if not ruta.is_file():
        return None, None
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        return None, None
    try:
        fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        captura.release()
    duracion = total / fps if total > 0 else 0.0
    inicio = resolver_inicio(ruta, cfg.video.inicio_grabacion, cfg.video.utc_offset_horas, duracion)
    return inicio, duracion


def _gpx_que_coincide(raiz: Path, video_rel: str, candidatos: list[str], cfg: Config) -> str:
    """El GPX que se solapa en el tiempo con el video; vacío si ninguno lo hace."""
    if not video_rel:
        return ""
    inicio, duracion = _duracion_video(raiz, video_rel, cfg)
    if inicio is None:
        return ""
    fin = inicio + timedelta(seconds=duracion)
    mejor, mejor_solape = "", 0.0
    for rel in candidatos:
        try:
            recorrido = Recorrido.desde_gpx(raiz / rel)
        except Exception:  # un GPX ilegible no debe romper el formulario
            continue
        solape = (min(fin, recorrido.fin) - max(inicio, recorrido.inicio)).total_seconds()
        if solape > mejor_solape:
            mejor, mejor_solape = rel, solape
    return mejor


def _valores(
    accion: cat.Accion, sugerencias: dict[str, list[str]], cfg: Config, raiz: Path
) -> dict[str, str]:
    """Valores con los que se abre el formulario: por defecto o tomados del proyecto."""
    valores: dict[str, str] = {}
    for campo in accion.campos:
        valor = campo.valor
        if campo.automatico == "gpx_del_video":
            valor = _gpx_que_coincide(raiz, valores.get("video", ""), sugerencias["gpx"], cfg) or valor
        elif campo.automatico and sugerencias.get(campo.automatico):
            valor = sugerencias[campo.automatico][0]
        elif campo.automatico == "db" and not sugerencias["db"]:
            valor = BD_PREDETERMINADA
        valores[campo.nombre] = valor
    return valores


def _validar(accion: cat.Accion, valores: dict[str, str], raiz: Path) -> list[str]:
    """Comprueba los campos antes de ejecutar, con mensajes claros en español."""
    errores: list[str] = []
    for campo in accion.campos:
        if campo.tipo == "casilla":
            continue
        valor = (valores.get(campo.nombre) or "").strip()
        if campo.requerido and not valor:
            errores.append(f"Falta «{campo.etiqueta}».")
        elif valor and campo.existe and not (raiz / valor).exists():
            errores.append(f"No existe «{valor}» ({campo.etiqueta}).")
        elif campo.tipo == "lista" and any(_parece_opcion(p) for p in cat.partes_de_lista(valor)):
            # Un valor como "Japan --vacias 0.9" metería otra opción en el comando.
            errores.append(f"«{campo.etiqueta}» no puede contener opciones que empiecen por «-».")
    if accion.requiere_uno_de:
        con_valor = [n for n in accion.requiere_uno_de if (valores.get(n) or "").strip()]
        etiquetas = [
            f"«{accion.campo(n).etiqueta}»" for n in accion.requiere_uno_de if accion.campo(n)
        ]
        if not con_valor:
            errores.append(f"Indique {' o '.join(etiquetas)}.")
        elif len(con_valor) > 1:
            # La CLI rechaza las dos a la vez (p. ej. --video y --camara); se avisa antes.
            errores.append(f"Indique solo uno: {' o '.join(etiquetas)}; deje vacío el otro.")
    return errores


def _parece_opcion(parte: str) -> bool:
    """True si `parte` se leería como una opción de la línea de comandos (no un número)."""
    if not parte.startswith("-"):
        return False
    try:
        float(parte)
    except ValueError:
        return True
    return False


def _bd_dentro(raiz: Path, db_rel: str) -> Path | None:
    """Ruta absoluta de la base de datos si está dentro del proyecto; None si sale de él."""
    ruta = (raiz / db_rel).resolve()
    return ruta if raiz in ruta.parents else None


def _salidas(raiz: Path) -> list[dict]:
    """Carpetas dentro de `salidas/` con lo que contienen, para la página de archivos."""
    base = raiz / "salidas"
    if not base.is_dir():
        return []
    resultado = []
    for carpeta in sorted(p for p in base.iterdir() if p.is_dir()):
        archivos = {p.name for p in carpeta.iterdir() if p.is_file()}
        recortes = carpeta / "recortes"
        resultado.append(
            {
                "nombre": carpeta.name,
                "rel": carpeta.relative_to(raiz).as_posix(),
                "mapa": "mapa.html" in archivos,
                "csv": "danos.csv" in archivos,
                "db": "danos.db" in archivos,
                "videos": sorted(p.name for p in carpeta.iterdir() if p.suffix.lower() == ".mp4"),
                "recortes": len(list(recortes.glob("*.jpg"))) if recortes.is_dir() else 0,
            }
        )
    return resultado


# ----------------------------------------------------------------------- app


def create_app(raiz: str | Path | None = None) -> Flask:
    """Crea la aplicación. `raiz` es la carpeta del proyecto (por defecto, la actual)."""
    raiz_resuelta = Path(raiz or Path.cwd()).resolve()
    app = Flask(__name__)
    app.config["RAIZ"] = raiz_resuelta
    app.config["EJECUTOR"] = Ejecutor(raiz_resuelta)
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000  # el formulario es diminuto; nada de subidas
    # Nombres de host aceptados en la cabecera Host; None desactiva la comprobación
    # (solo cuando se arranca a propósito con --host distinto de 127.0.0.1).
    app.config["HOSTS_PERMITIDOS"] = HOSTS_LOCALES
    _registrar_rutas(app)
    return app


HOSTS_LOCALES = frozenset({"127.0.0.1", "localhost", "::1"})


def _nombre_host(valor: str) -> str:
    """El nombre de host sin puerto ni corchetes ('[::1]:5000' -> '::1')."""
    return (urlsplit(f"//{valor}").hostname or "").lower()


def _registrar_rutas(app: Flask) -> None:
    def raiz() -> Path:
        return app.config["RAIZ"]

    @app.before_request
    def proteger():
        """Rechaza peticiones que no vienen de la propia interfaz.

        Sin esto, cualquier página abierta en el navegador mientras corre el servidor
        podría enviar un formulario a http://127.0.0.1:5000/accion/... (CSRF) y lanzar
        comandos o sobrescribir archivos; y con DNS rebinding podría además leer
        /archivo/... La cabecera Host debe ser local, y en los POST el Origin (o el
        Referer) debe ser el propio servidor. Los clientes que no mandan ninguna de las
        dos (curl, las pruebas) no son navegadores y no están expuestos a CSRF.
        """
        permitidos = app.config["HOSTS_PERMITIDOS"]
        if permitidos is not None and _nombre_host(request.host) not in permitidos:
            abort(403)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        origen = request.headers.get("Origin") or request.headers.get("Referer")
        if origen is not None and urlsplit(origen).netloc.lower() != request.host.lower():
            abort(403)
        return None

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            grupos=cat.por_grupo(),
            trabajos=app.config["EJECUTOR"].recientes(),
            salidas=_salidas(raiz())[:6],
        )

    @app.get("/accion/<accion_id>")
    def accion(accion_id: str):
        definicion = cat.por_id(accion_id)
        if definicion is None:
            abort(404)
        return render_template(
            "accion.html",
            accion=definicion,
            sugerencias=_sugerencias(raiz()),
            valores=_valores(definicion, _sugerencias(raiz()), _config(raiz()), raiz()),
            errores=[],
        )

    @app.post("/accion/<accion_id>")
    def ejecutar(accion_id: str):
        definicion = cat.por_id(accion_id)
        if definicion is None:
            abort(404)
        valores = {campo.nombre: request.form.get(campo.nombre, "") for campo in definicion.campos}
        errores = _validar(definicion, valores, raiz())
        if errores:
            return (
                render_template(
                    "accion.html",
                    accion=definicion,
                    sugerencias=_sugerencias(raiz()),
                    valores=valores,
                    errores=errores,
                ),
                400,
            )
        trabajo = app.config["EJECUTOR"].iniciar(definicion, valores)
        return redirect(url_for("trabajo", trabajo_id=trabajo.id))

    @app.errorhandler(403)
    def prohibido(_error):
        return (
            "Petición rechazada: la interfaz solo acepta acciones enviadas desde su propia "
            "página (http://127.0.0.1).",
            403,
        )

    @app.post("/api/comando/<accion_id>")
    def api_comando(accion_id: str):
        """Vista previa: el comando exacto que se ejecutará con lo que hay en el formulario."""
        definicion = cat.por_id(accion_id)
        if definicion is None:
            return jsonify({"error": "no existe"}), 404
        datos = request.get_json(silent=True) or {}
        valores = {campo.nombre: str(datos.get(campo.nombre, "")) for campo in definicion.campos}
        return jsonify({"comando": "python " + " ".join(definicion.argv(valores))})

    @app.get("/api/gpx")
    def api_gpx():
        """Busca el GPX que coincide con un video, para el botón del formulario."""
        video = request.args.get("video", "")
        gpx = _gpx_que_coincide(raiz(), video, _sugerencias(raiz())["gpx"], _config(raiz()))
        return jsonify({"gpx": gpx})

    @app.get("/trabajo/<trabajo_id>")
    def trabajo(trabajo_id: str):
        actual = app.config["EJECUTOR"].obtener(trabajo_id)
        if actual is None:
            abort(404)
        lineas, total = actual.leer(0)
        return render_template("trabajo.html", trabajo=actual.instantanea(), lineas=lineas, total=total)

    @app.get("/api/trabajo/<trabajo_id>")
    def api_trabajo(trabajo_id: str):
        actual = app.config["EJECUTOR"].obtener(trabajo_id)
        if actual is None:
            return jsonify({"error": "no existe"}), 404
        desde = request.args.get("desde", type=int, default=0)
        datos = actual.instantanea()
        # Líneas y total salen de la misma lectura: si no, entre una y otra pueden llegar
        # líneas nuevas y el navegador las pediría dos veces.
        datos["lineas"], datos["total"] = actual.leer(desde)
        return jsonify(datos)

    @app.get("/salidas")
    def lista_salidas():
        return render_template("salidas.html", salidas=_salidas(raiz()))

    @app.get("/revisar")
    def revisar():
        db_rel = request.args.get("db") or BD_PREDETERMINADA
        modo = request.args.get("modo", "pendientes")
        clase = request.args.get("clase", "")
        ruta_db = _bd_dentro(raiz(), db_rel)
        contexto = {
            "db": db_rel,
            "modo": modo,
            "clase": clase,
            "clases": [],
            "filas": [],
            "cuenta": {"total": 0, "revisados": 0, "reales": 0, "pendientes": 0},
            "error": None,
        }
        if ruta_db is None or not ruta_db.is_file():
            contexto["error"] = (
                f"No existe la base de datos {db_rel} dentro del proyecto. Use otra ruta o "
                "ejecute antes «Procesar un recorrido»."
            )
            return render_template("revisar.html", **contexto)

        try:
            with BaseDatos(ruta_db) as bd:
                todas = bd.danos()
        except sqlite3.DatabaseError as error:
            contexto["error"] = f"{db_rel} no es una base de datos de TapaHuecos ({error})."
            return render_template("revisar.html", **contexto)
        contexto["clases"] = sorted({f["clase"] for f in todas})
        revisados = sum(1 for f in todas if f["verificado"] is not None)
        reales = sum(1 for f in todas if f["verificado"] == 1)
        contexto["cuenta"] = {
            "total": len(todas),
            "revisados": revisados,
            "reales": reales,
            "pendientes": len(todas) - revisados,
        }

        filas = [f for f in todas if f["verificado"] is None] if modo == "pendientes" else todas
        if clase:
            filas = [f for f in filas if f["clase"] == clase]
        prefijo = Path(db_rel).parent.as_posix()
        for fila in filas:
            fila["url"] = url_for("archivo", ruta=f"{prefijo}/{fila['recorte']}")
        contexto["filas"] = filas
        return render_template("revisar.html", **contexto)

    @app.post("/api/revisar")
    def api_revisar():
        datos = request.get_json(silent=True) or {}
        db_rel = str(datos.get("db") or BD_PREDETERMINADA)
        ruta_db = _bd_dentro(raiz(), db_rel)
        if ruta_db is None or not ruta_db.is_file():
            return jsonify({"ok": False, "error": "no existe la base de datos"}), 404
        try:
            dano_id = int(datos["id"])
            real = bool(datos["real"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"ok": False, "error": "faltan id o real"}), 400
        try:
            with BaseDatos(ruta_db) as bd:
                bd.marcar(dano_id, real)
                todas = bd.danos()
        except sqlite3.DatabaseError as error:
            return jsonify({"ok": False, "error": f"base de datos inválida: {error}"}), 400
        revisados = sum(1 for f in todas if f["verificado"] is not None)
        return jsonify(
            {
                "ok": True,
                "revisados": revisados,
                "reales": sum(1 for f in todas if f["verificado"] == 1),
                "pendientes": len(todas) - revisados,
            }
        )

    @app.get("/archivo/<path:ruta>")
    def archivo(ruta: str):
        destino = (raiz() / ruta).resolve()
        if destino != raiz() and raiz() not in destino.parents:
            abort(404)
        if not destino.is_file():
            abort(404)
        return send_from_directory(destino.parent, destino.name)


def main() -> None:
    """Levanta el servidor local. Pensado para correr desde la carpeta del proyecto."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Interfaz web local de TapaHuecos (ejecuta los comandos desde el navegador)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="por defecto: %(default)s")
    parser.add_argument("--puerto", type=int, default=5000, help="por defecto: %(default)s")
    parser.add_argument("--depurar", action="store_true", help="modo de depuración de Flask")
    args = parser.parse_args()
    app = create_app()
    if _nombre_host(args.host) not in HOSTS_LOCALES:
        if args.depurar:
            parser.error("--depurar solo se permite con --host 127.0.0.1: el depurador de "
                         "Flask ejecuta código y quedaría expuesto a la red.")
        print(f"AVISO: escuchando en {args.host}. Cualquiera en la misma red podrá ejecutar "
              "acciones y leer los archivos del proyecto; la interfaz no tiene contraseña.")
        app.config["HOSTS_PERMITIDOS"] = None
    print(f"TapaHuecos web en http://{args.host}:{args.puerto}  (Ctrl+C para salir)")
    app.run(host=args.host, port=args.puerto, debug=args.depurar)
