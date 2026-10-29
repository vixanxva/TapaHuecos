"""Interfaz de consola: `tapahuecos <comando>` o `python -m tapahuecos <comando>`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tapahuecos import __version__
from tapahuecos.config import cargar_config

log = logging.getLogger("tapahuecos")

CONFIG_PREDETERMINADA = Path("config.yaml")
BD_PREDETERMINADA = Path("salidas/danos.db")


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
        cfg.video.inicio_grabacion = args.inicio

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
        raise SystemExit(f"No existe la base de datos {ruta}. Ejecute primero `procesar`.")
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


def _argumentos_bd(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=BD_PREDETERMINADA, help="base de datos SQLite")
    parser.add_argument("--recorrido", type=int, help="limitar a un recorrido (ID)")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tapahuecos",
        description="Detector de daños en las vías (huecos y grietas) a partir de video y GPS.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="mensajes de depuración")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("procesar", help="procesa un video y genera todas las salidas")
    fuente = p.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--video", type=Path, help="video grabado desde el vehículo")
    fuente.add_argument("--camara", type=int, metavar="INDICE", help="cámara en vivo (ej. 0)")
    p.add_argument("--gpx", type=Path, help="recorrido GPS grabado al mismo tiempo que el video")
    p.add_argument("--config", type=Path, help="archivo YAML (por defecto config.yaml si existe)")
    p.add_argument("--salida", type=Path, default=Path("salidas"), help="carpeta de resultados")
    p.add_argument("--pesos", help="modelo YOLO (.pt); reemplaza el de la configuración")
    p.add_argument("--cada", type=int, metavar="N", help="procesar 1 de cada N fotogramas")
    p.add_argument("--inicio", help="hora de inicio del video, ISO 8601 (ej. 2026-10-29T14:30:15)")
    p.add_argument("--mostrar", action="store_true", help="mostrar el video mientras se procesa")
    p.set_defaults(funcion=_cmd_procesar)

    m = sub.add_parser("mapa", help="regenera el mapa HTML desde la base de datos")
    _argumentos_bd(m)
    m.add_argument("--salida", type=Path, help="ruta del HTML (por defecto junto a la BD)")
    m.add_argument("--todos", action="store_true",
                   help="un punto por registro, sin agrupar los daños repetidos entre recorridos")
    m.set_defaults(funcion=_cmd_mapa)

    f = sub.add_parser("fusionar", help="agrupa el mismo daño registrado en varios recorridos")
    f.add_argument("--db", type=Path, default=BD_PREDETERMINADA, help="base de datos SQLite")
    f.add_argument("--radio", type=float, default=8.0, help="distancia máxima en metros")
    f.add_argument("--cualquier-clase", action="store_true",
                   help="agrupar aunque la clase no coincida (por defecto debe coincidir)")
    f.set_defaults(funcion=_cmd_fusionar)

    e = sub.add_parser("exportar", help="exporta la base de datos a CSV")
    _argumentos_bd(e)
    e.add_argument("--csv", type=Path, help="ruta del CSV (por defecto junto a la BD)")
    e.set_defaults(funcion=_cmd_exportar)

    r = sub.add_parser("resumen", help="tabla de daños por clase")
    _argumentos_bd(r)
    r.set_defaults(funcion=_cmd_resumen)

    v = sub.add_parser("revisar", help="marca cada daño como real o falso positivo")
    _argumentos_bd(v)
    v.add_argument("--todos", action="store_true", help="incluir los ya revisados")
    v.set_defaults(funcion=_cmd_revisar)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.funcion(args)
    except (FileNotFoundError, ValueError, OSError) as error:
        log.error("%s", error)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130
