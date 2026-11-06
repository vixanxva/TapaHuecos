"""Interfaz de consola: `tapahuecos <comando>` o `python -m tapahuecos <comando>`."""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path

from gpxpy.gpx import GPXException

from tapahuecos import __version__
from tapahuecos.config import cargar_config, validar_region

log = logging.getLogger("tapahuecos")

CONFIG_PREDETERMINADA = Path("config.yaml")
BD_PREDETERMINADA = Path("salidas/danos.db")

# Mensajes de argparse traducidos. Si una versión de Python cambia el texto original,
# el mensaje sale en inglés pero el programa se comporta igual.
_ERRORES_ARGPARSE = [
    (r"^argument ([^:]+): ", r"\1: "),
    (r"one of the arguments (.+) is required", r"falta una de estas opciones: \1"),
    (r"the following arguments are required: (.+)", r"falta: \1"),
    (r"not allowed with argument (.+)", r"no se puede usar junto con \1"),
    (r"invalid \w+ value: (.+)", r"valor no válido: \1 (debe ser un número)"),
    (r"invalid choice: (.+?) \(choose from (.+)\)", r"\1 no existe; las opciones son: \2"),
    (r"unrecognized arguments: (.+)", r"opción no reconocida: \1"),
    (r"expected one argument", r"falta el valor"),
]


def _traducir_error(mensaje: str) -> str:
    for patron, reemplazo in _ERRORES_ARGPARSE:
        mensaje = re.sub(patron, reemplazo, mensaje)
    return mensaje


class _FormatoAyuda(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser con la ayuda y los errores en español."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _FormatoAyuda)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opciones"
        self.add_argument("-h", "--help", action="help", help="muestra esta ayuda y termina")

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(
            2,
            f"{self.prog}: error: {_traducir_error(message)}\n"
            f"Use `{self.prog} --help` para ver las opciones.\n",
        )


def _cmd_procesar(args: argparse.Namespace) -> int:
    from tapahuecos.pipeline import procesar

    ruta_config = args.config
    if ruta_config is None and CONFIG_PREDETERMINADA.exists():
        ruta_config = CONFIG_PREDETERMINADA
    cfg = cargar_config(ruta_config)
    if args.pesos:
        cfg.modelo.pesos = args.pesos
    if args.cada:
        cfg.video.cada_n_fotogramas = args.cada
    if args.inicio:
        from tapahuecos.entrada import interpretar_fecha

        try:
            interpretar_fecha(args.inicio, cfg.video.utc_offset_horas)
        except ValueError:
            log.error(
                "--inicio debe ser una fecha y hora ISO 8601, ej. 2026-10-29T14:30:15 (se recibió %r)",
                args.inicio,
            )
            return 1
        cfg.video.inicio_grabacion = args.inicio
    if args.region:
        try:
            cfg.video.region = [float(v) for v in args.region.split(",")]
            validar_region(cfg.video.region)
        except ValueError:
            log.error(
                "--region debe ser x1,y1,x2,y2 con números entre 0 y 1, x1 < x2 y y1 < y2 "
                "(ej. 0,0.45,1,1 = franja inferior); se recibió %r",
                args.region,
            )
            return 1

    if args.video is not None and not args.video.exists():
        log.error("No existe el video %s", args.video)
        return 1
    if args.gpx is not None and not args.gpx.exists():
        log.error("No existe el GPX %s", args.gpx)
        return 1
    if args.gpx is None:
        log.warning("Sin --gpx: los daños se registrarán sin coordenadas.")

    origen = args.video if args.video is not None else args.camara
    r = procesar(origen, cfg, args.salida, args.gpx, mostrar=args.mostrar or args.camara is not None)
    print(
        f"\nListo. {r.fotogramas_procesados} fotogramas en {r.segundos:.1f} s "
        f"({r.fps:.1f} fps), {r.danos_registrados} daños registrados.\n"
        f"  Video anotado : {r.video_anotado}\n"
        f"  Recortes      : {r.base_datos.parent / 'recortes'}\n"
        f"  Base de datos : {r.base_datos}\n"
        f"  CSV           : {r.csv}\n"
        f"  Mapa          : {r.mapa}"
    )
    return 0


def _abrir_bd(ruta: Path):
    from tapahuecos.registro import BaseDatos

    if not ruta.exists():
        raise SystemExit(
            f"No existe la base de datos {ruta}. Ejecute primero `tapahuecos procesar`, "
            f"o indique otra con --db (la ruta se busca desde la carpeta actual: {Path.cwd()})."
        )
    return BaseDatos(ruta)


def _cmd_mapa(args: argparse.Namespace) -> int:
    from tapahuecos.fusion import unicos
    from tapahuecos.salidas import generar_mapa

    with _abrir_bd(args.db) as bd:
        filas = bd.danos(args.recorrido)
    if not args.todos:
        filas = unicos(filas)
    ruta = generar_mapa(filas, args.salida or args.db.parent / "mapa.html", args.db.parent)
    print(f"Mapa con {len(filas)} daños: {ruta}")
    return 0


def _cmd_fusionar(args: argparse.Namespace) -> int:
    from tapahuecos.fusion import fusionar_bd

    with _abrir_bd(args.db) as bd:
        registros, unicos = fusionar_bd(bd, args.radio, misma_clase=not args.cualquier_clase)
    print(
        f"{registros} registros -> {unicos} daños únicos (radio {args.radio:g} m). "
        "Regenere el mapa con `tapahuecos mapa`."
    )
    return 0


def _cmd_exportar(args: argparse.Namespace) -> int:
    from tapahuecos.salidas import exportar_csv

    with _abrir_bd(args.db) as bd:
        filas = bd.danos(args.recorrido)
    ruta = exportar_csv(filas, args.csv or args.db.parent / "danos.csv")
    print(f"{len(filas)} filas exportadas a {ruta}")
    return 0


def _cmd_resumen(args: argparse.Namespace) -> int:
    from tapahuecos.salidas import resumen

    with _abrir_bd(args.db) as bd:
        tabla = resumen(bd.danos(args.recorrido))
    print("No hay daños registrados." if tabla.empty else tabla.to_string(index=False))
    return 0


def _cmd_revisar(args: argparse.Namespace) -> int:
    """Muestra cada recorte para marcarlo como daño real (r) o falso positivo (f)."""
    import cv2

    with _abrir_bd(args.db) as bd:
        filas = [f for f in bd.danos(args.recorrido) if args.todos or f["verificado"] is None]
        if not filas:
            print("No hay daños pendientes de revisión.")
            return 0
        print("Teclas: [r] real · [f] falso positivo · [o] omitir · [q] salir")
        ventana = "Revisar (r/f/o/q)"
        for i, fila in enumerate(filas, 1):
            imagen = cv2.imread(str(args.db.parent / fila["recorte"]))
            if imagen is None:
                log.warning("No se encontró el recorte %s", fila["recorte"])
                continue
            escala = max(1.0, 360 / max(imagen.shape[:2]))
            imagen = cv2.resize(imagen, None, fx=escala, fy=escala)
            texto = f"{i}/{len(filas)}  {fila['clase']} {fila['nombre_clase']}  {fila['confianza']:.2f}"
            cv2.putText(imagen, texto, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
            cv2.putText(imagen, texto, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            cv2.imshow(ventana, imagen)
            while True:
                tecla = chr(cv2.waitKey(0) & 0xFF).lower()
                if tecla in "rf":
                    bd.marcar(fila["id"], tecla == "r")
                if tecla in "rfo":
                    break
                if tecla == "q":
                    cv2.destroyAllWindows()
                    return 0
        cv2.destroyAllWindows()
    print("Revisión terminada. Calcule las métricas con scripts/evaluar.py campo.")
    return 0


AYUDA_DB = "base de datos SQLite (por defecto: %(default)s, desde la carpeta actual)"


def _argumentos_bd(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=BD_PREDETERMINADA, help=AYUDA_DB)
    parser.add_argument("--recorrido", type=int, metavar="ID",
                        help="limitar a un recorrido: cada `procesar` crea uno nuevo "
                             "(columna recorrido_id de danos.csv)")


def construir_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="tapahuecos",
        description="Detector de daños en las vías (huecos y grietas) a partir de video y GPS.\n"
                    "Ejecute los comandos desde la carpeta del proyecto, donde está config.yaml.",
        epilog="Use `tapahuecos COMANDO --help` para ver las opciones de cada comando.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}",
                        help="muestra la versión y termina")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="muestra mensajes de depuración (útil para reportar un error)")
    sub = parser.add_subparsers(dest="comando", required=True, title="comandos")

    p = sub.add_parser(
        "procesar", help="procesa un video y genera todas las salidas",
        description="Procesa un video grabado (--video) o la cámara en vivo (--camara) y deja en\n"
                    "--salida el video anotado, los recortes, danos.db, danos.csv y mapa.html.",
        epilog="ejemplo:\n  tapahuecos procesar --video datos/videos/VID_20261029_143015.mp4 "
               "--gpx datos/gpx/20261029.gpx --pesos modelos/best_rdd.pt",
    )
    fuente = p.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--video", type=Path,
                        help="video grabado desde el vehículo (.mp4); la hora de inicio se toma del "
                             "nombre VID_AAAAMMDD_HHMMSS o de --inicio")
    fuente.add_argument("--camara", type=int, metavar="INDICE",
                        help="cámara en vivo (0 = la del portátil); abre una ventana, [q] para terminar")
    p.add_argument("--gpx", type=Path,
                   help="recorrido GPS grabado al mismo tiempo que el video; sin él, los daños "
                        "quedan sin coordenadas")
    p.add_argument("--config", type=Path,
                   help="archivo YAML de parámetros (por defecto config.yaml de la carpeta actual, "
                        "si existe)")
    p.add_argument("--salida", type=Path, default=Path("salidas"),
                   help="carpeta de resultados (por defecto: %(default)s)")
    p.add_argument("--pesos", metavar="ARCHIVO.pt",
                   help="modelo YOLO entrenado, ej. modelos/best_rdd.pt (por defecto: modelo.pesos "
                        "de config.yaml)")
    p.add_argument("--cada", type=int, metavar="N",
                   help="procesar 1 de cada N fotogramas; más alto = más rápido (por defecto: "
                        "video.cada_n_fotogramas de config.yaml)")
    p.add_argument("--inicio", metavar="FECHA_HORA",
                   help="hora local de inicio del video, ISO 8601 (ej. 2026-10-29T14:30:15); "
                        "hace falta si el nombre del video no la trae")
    p.add_argument("--region", metavar="X1,Y1,X2,Y2",
                   help="analizar solo esa parte del fotograma, en fracciones (ej. 0,0.45,1,1)")
    p.add_argument("--mostrar", action="store_true",
                   help="mostrar el video mientras se procesa ([q] para detener); necesita "
                        "ventana, no sirve en Colab")
    p.set_defaults(funcion=_cmd_procesar)

    m = sub.add_parser("mapa", help="regenera el mapa HTML desde la base de datos")
    _argumentos_bd(m)
    m.add_argument("--salida", type=Path, help="ruta del HTML (por defecto: mapa.html junto a la BD)")
    m.add_argument("--todos", action="store_true",
                   help="un punto por registro, sin agrupar los daños repetidos entre recorridos")
    m.set_defaults(funcion=_cmd_mapa)

    f = sub.add_parser("fusionar", help="agrupa el mismo daño registrado en varios recorridos")
    f.add_argument("--db", type=Path, default=BD_PREDETERMINADA, help=AYUDA_DB)
    f.add_argument("--radio", type=float, default=8.0,
                   help="distancia máxima en metros entre dos registros del mismo daño "
                        "(por defecto: %(default)s)")
    f.add_argument("--cualquier-clase", action="store_true",
                   help="agrupar aunque la clase no coincida (por defecto debe coincidir)")
    f.set_defaults(funcion=_cmd_fusionar)

    e = sub.add_parser("exportar", help="exporta la base de datos a CSV")
    _argumentos_bd(e)
    e.add_argument("--csv", type=Path, help="ruta del CSV (por defecto: danos.csv junto a la BD)")
    e.set_defaults(funcion=_cmd_exportar)

    r = sub.add_parser("resumen", help="tabla de daños por clase")
    _argumentos_bd(r)
    r.set_defaults(funcion=_cmd_resumen)

    v = sub.add_parser(
        "revisar", help="marca cada daño como real o falso positivo",
        description="Abre una ventana con cada recorte para marcarlo: [r] real, [f] falso positivo,\n"
                    "[o] omitir, [q] salir. Necesita pantalla: no funciona en Colab.",
    )
    _argumentos_bd(v)
    v.add_argument("--todos", action="store_true", help="incluir los ya revisados")
    v.set_defaults(funcion=_cmd_revisar)
    return parser


def _mensaje_archivo_faltante(error: FileNotFoundError, args: argparse.Namespace) -> str:
    ruta = error.filename
    if ruta is None:
        if args.comando == "procesar" and "modelo" in str(error):
            return (f"{error} Si ya tiene los pesos (ver modelos/README.md), cópielos en modelos/ "
                    "y use --pesos modelos/best_rdd.pt.")
        return str(error)
    if str(ruta).endswith(".pt"):
        return (f"No existe el modelo {ruta}. Descargue los pesos (ver modelos/README.md) "
                "o indique la ruta con --pesos, ej. --pesos modelos/best_rdd.pt.")
    return (f"No existe el archivo {ruta}. Revise la ruta: las rutas relativas se buscan desde "
            f"la carpeta actual ({Path.cwd()}).")


def _pista_fuente_video(args: argparse.Namespace) -> str | None:
    if getattr(args, "camara", None) is not None:
        return (f"Revise que la cámara {args.camara} esté conectada y que ningún otro programa "
                "(Zoom, Teams, la app Cámara) la esté usando, o pruebe otro índice: --camara 1.")
    if getattr(args, "video", None) is not None:
        return "El archivo puede estar dañado, incompleto o en un formato que OpenCV no lee (use .mp4)."
    return None


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.funcion(args)
    except FileNotFoundError as error:
        log.error("%s", _mensaje_archivo_faltante(error, args))
        return 1
    except GPXException as error:
        log.error("No se pudo leer el GPX %s (%s). Revise que sea el .gpx completo que exportó "
                  "la app de GPS.", getattr(args, "gpx", ""), error)
        return 1
    except sqlite3.DatabaseError as error:
        ruta = getattr(args, "db", None) or Path(getattr(args, "salida", "salidas")) / "danos.db"
        log.error("No se pudo leer %s como base de datos de TapaHuecos (%s). Indique otra con --db, "
                  "o bórrela y vuelva a ejecutar `tapahuecos procesar`.", ruta, error)
        return 1
    except (ValueError, OSError) as error:
        log.error("%s", error)
        if isinstance(error, OSError) and str(error).startswith("No se pudo abrir la fuente de video"):
            pista = _pista_fuente_video(args)
            if pista:
                log.error("%s", pista)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130
