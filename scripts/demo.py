"""Genera un video y un GPX de demostración para correr `tapahuecos procesar` sin recorridos reales.

El video se arma con imágenes de una carpeta (por ejemplo, la partición de prueba de RDD2022
convertida con scripts/preparar_rdd2022.py). Si junto a la carpeta hay etiquetas YOLO, se
prefieren las imágenes con daños y, entre ellas, las que tienen huecos (D40). Las etiquetas se
buscan en `images/<split>` -> `labels/<split>` o en `<split>/images` -> `<split>/labels`.

Cada imagen se muestra unos segundos con un acercamiento progresivo hacia la parte inferior,
como si el vehículo avanzara, para que el seguidor conserve el mismo ID. Entre una imagen y la
siguiente se insertan unos fotogramas negros para que el seguidor cierre la pista.

El GPX simula un recorrido a velocidad constante por la Avenida Primera de Montería, junto al
río Sinú, y cubre toda la duración del video. El video se llama VID_AAAAMMDD_HHMMSS.mp4 para
que el pipeline deduzca la hora de inicio.

Los resultados son de DEMOSTRACIÓN, no de campo: las imágenes no son de Montería.

Uso:
    python scripts/demo.py --imagenes datos/rdd_yolo/images/test
    python scripts/demo.py --imagenes datos/rdd_yolo/images/test --cantidad 30 --inicio 2026-10-29T14:30:00
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import gpxpy.gpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tapahuecos.clases import CODIGOS  # noqa: E402
from tapahuecos.entrada import interpretar_fecha  # noqa: E402
from tapahuecos.gps import distancia_m  # noqa: E402

EXTENSIONES = (".jpg", ".jpeg", ".png")
INDICE_HUECO = CODIGOS.index("D40")

# Avenida Primera (Avenida Carrera 1) de Montería, de sur a norte por la orilla oriental del
# río Sinú, desde el sur del centro hasta pasar la Calle 41. Puntos tomados de la geometría
# de OpenStreetMap (vías "Avenida 1" y "Avenida Carrera 1", consultadas el 29/10/2026) y
# simplificados; entre 8.7618 y 8.7632 de latitud OSM no trae el tramo con ese nombre y se
# unen en línea recta. Son unos 2.2 km. El sentido norte es el de circulación de la vía; si
# el video dura más que el recorrido, la ruta se recorre de ida y vuelta (solo es una demo).
RUTA_MONTERIA: tuple[tuple[float, float], ...] = (
    (8.74798, -75.89157),
    (8.74923, -75.89143),
    (8.75079, -75.89133),
    (8.75208, -75.89120),
    (8.75279, -75.89093),
    (8.75374, -75.89017),
    (8.75493, -75.88924),
    (8.75629, -75.88816),
    (8.75801, -75.88683),
    (8.75916, -75.88602),
    (8.76055, -75.88501),
    (8.76181, -75.88401),
    (8.76316, -75.88362),
    (8.76434, -75.88332),
    (8.76564, -75.88273),
    (8.76681, -75.88239),
)

# Altura (fracción desde arriba) del punto que queda fijo durante el acercamiento.
FRACCION_PUNTO_FIJO = 2 / 3

# Valores de config.yaml con los que se comprueba que cada imagen alcance a registrarse.
CADA_N_FOTOGRAMAS = 2
MIN_FOTOGRAMAS = 3


# --- Selección de imágenes ---------------------------------------------------------------


def carpeta_etiquetas(carpeta_imagenes: Path) -> Path | None:
    """Carpeta de etiquetas YOLO hermana de la de imágenes, si existe."""
    carpeta = Path(carpeta_imagenes)
    candidatas = []
    if carpeta.parent.name == "images":  # images/<split> -> labels/<split>
        candidatas.append(carpeta.parent.parent / "labels" / carpeta.name)
    if carpeta.name == "images":  # <split>/images -> <split>/labels
        candidatas.append(carpeta.parent / "labels")
    return next((c for c in candidatas if c.is_dir()), None)


def clases_etiquetadas(ruta_etiqueta: Path) -> set[int]:
    """Índices de clase presentes en un archivo de etiquetas YOLO (vacío si no existe)."""
    if not ruta_etiqueta.exists():
        return set()
    clases = set()
    for linea in ruta_etiqueta.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if partes:
            try:
                clases.add(int(float(partes[0])))
            except ValueError:
                continue
    return clases


def seleccionar_imagenes(carpeta: Path, cantidad: int, azar: random.Random) -> list[Path]:
    """Elige `cantidad` imágenes: primero las que tienen huecos, luego otros daños, luego el resto."""
    imagenes = sorted(
        p for p in Path(carpeta).iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES
    )
    if not imagenes:
        raise SystemExit(f"No hay imágenes .jpg, .jpeg o .png en {carpeta}")

    etiquetas = carpeta_etiquetas(carpeta)
    if etiquetas is None:
        grupos = [imagenes]
    else:
        con_hueco, con_dano, sin_dano = [], [], []
        for imagen in imagenes:
            clases = clases_etiquetadas(etiquetas / f"{imagen.stem}.txt")
            if INDICE_HUECO in clases:
                con_hueco.append(imagen)
            elif clases:
                con_dano.append(imagen)
            else:
                sin_dano.append(imagen)
        grupos = [con_hueco, con_dano, sin_dano]

    elegidas: list[Path] = []
    for grupo in grupos:
        grupo = list(grupo)
        azar.shuffle(grupo)
        elegidas.extend(grupo[: max(0, cantidad - len(elegidas))])
    azar.shuffle(elegidas)  # mezcla huecos y grietas a lo largo del video
    return elegidas


# --- Fotogramas -----------------------------------------------------------------------------


def leer_imagen(ruta: Path) -> np.ndarray | None:
    """cv2.imread no abre rutas con tildes en Windows; imdecode sí."""
    datos = np.fromfile(str(ruta), dtype=np.uint8)
    return cv2.imdecode(datos, cv2.IMREAD_COLOR) if datos.size else None


def letterbox(imagen: np.ndarray, ancho: int, alto: int, zoom: float = 1.0) -> np.ndarray:
    """Ajusta la imagen a ancho x alto sin deformarla (franjas negras) y la acerca `zoom` veces.

    El acercamiento se hace hacia la parte inferior central, donde está la vía delante del
    vehículo: el punto fijo está en el centro horizontal y a `FRACCION_PUNTO_FIJO` de la altura.
    Así se recorta sobre todo el cielo, se conserva casi toda la vía y los daños de la parte
    baja crecen y bajan un poco, como al acercarse a ellos. El acercamiento se queda dentro del
    área de la imagen (las franjas no cambian) y usa una transformación afín con escala real
    para que sea suave, sin los saltos de un recorte en píxeles enteros.
    """
    h, w = imagen.shape[:2]
    escala = min(ancho / w, alto / h)
    nw, nh = max(1, round(w * escala)), max(1, round(h * escala))
    ox, oy = (ancho - nw) // 2, (alto - nh) // 2

    zoom = max(1.0, zoom)
    sx, sy = nw / w * zoom, nh / h * zoom
    # El punto fijo (px, py) de la imagen original cae en (qx, qy) de la salida con cualquier zoom.
    px, py = w / 2, h * FRACCION_PUNTO_FIJO
    qx, qy = ox + nw / 2, oy + nh * FRACCION_PUNTO_FIJO
    matriz = np.float32([[sx, 0, qx - px * sx], [0, sy, qy - py * sy]])
    salida = cv2.warpAffine(
        imagen, matriz, (ancho, alto), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0),
    )
    # Con zoom la imagen se sale de su área: se restauran las franjas negras.
    salida[:oy] = 0
    salida[oy + nh:] = 0
    salida[:, :ox] = 0
    salida[:, ox + nw:] = 0
    return salida


def fotogramas_por_imagen(segundos_por_imagen: float, fps: float) -> int:
    return max(1, round(segundos_por_imagen * fps))


def total_fotogramas(n_imagenes: int, por_imagen: int, separacion: int) -> int:
    return n_imagenes * por_imagen + max(0, n_imagenes - 1) * separacion


def escribir_video(
    imagenes: Sequence[np.ndarray | Path],
    ruta: Path,
    ancho: int,
    alto: int,
    fps: float,
    segundos_por_imagen: float,
    separacion: int = 3,
    zoom_final: float = 1.15,
    codec: str = "mp4v",
) -> int:
    """Escribe el video y devuelve el número de fotogramas.

    Cada imagen dura `segundos_por_imagen` con un acercamiento de 1.0x a `zoom_final`, y entre
    imágenes van `separacion` fotogramas negros. Las imágenes que no se pueden leer se omiten.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*codec), fps, (ancho, alto))
    if not escritor.isOpened():
        raise OSError(f"OpenCV no pudo crear el video {ruta} con el códec {codec}")

    n = fotogramas_por_imagen(segundos_por_imagen, fps)
    negro = np.zeros((alto, ancho, 3), np.uint8)
    escritos = 0
    primera = True
    try:
        for elemento in imagenes:
            imagen = leer_imagen(elemento) if isinstance(elemento, Path) else elemento
            if imagen is None:
                print(f"Aviso: no se pudo leer {elemento}; se omite.")
                continue
            if not primera:
                for _ in range(separacion):
                    escritor.write(negro)
                    escritos += 1
            primera = False
            for i in range(n):
                avance = i / (n - 1) if n > 1 else 0.0
                escritor.write(letterbox(imagen, ancho, alto, 1.0 + (zoom_final - 1.0) * avance))
                escritos += 1
    finally:
        escritor.release()
    return escritos


# --- GPX ---------------------------------------------------------------------------------


def _distancias_acumuladas(ruta: Sequence[tuple[float, float]]) -> list[float]:
    acumuladas = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(ruta, ruta[1:], strict=False):
        acumuladas.append(acumuladas[-1] + distancia_m(lat1, lon1, lat2, lon2))
    return acumuladas


def posicion_en_ruta(
    ruta: Sequence[tuple[float, float]], acumuladas: Sequence[float], distancia: float
) -> tuple[float, float]:
    """Punto a `distancia` metros del inicio; si se pasa del final, se devuelve (ida y vuelta)."""
    largo = acumuladas[-1]
    if largo <= 0:
        return ruta[0]
    distancia %= 2 * largo
    if distancia > largo:
        distancia = 2 * largo - distancia
    for i in range(1, len(acumuladas)):
        if distancia <= acumuladas[i]:
            tramo = acumuladas[i] - acumuladas[i - 1]
            f = (distancia - acumuladas[i - 1]) / tramo if tramo else 0.0
            (lat1, lon1), (lat2, lon2) = ruta[i - 1], ruta[i]
            return lat1 + f * (lat2 - lat1), lon1 + f * (lon2 - lon1)
    return ruta[-1]


def puntos_gpx(
    inicio: datetime,
    duracion_s: float,
    velocidad_kmh: float = 20.0,
    margen_s: int = 5,
    ruta: Sequence[tuple[float, float]] = RUTA_MONTERIA,
) -> list[tuple[datetime, float, float]]:
    """Un punto (hora UTC, latitud, longitud) por segundo, de `margen_s` antes del inicio del
    video a `margen_s` después del final, avanzando a velocidad constante por la ruta.

    El vehículo está en el primer punto de la ruta cuando empieza el video.
    """
    if inicio.tzinfo is None:
        raise ValueError("inicio debe tener zona horaria")
    inicio_utc = inicio.astimezone(timezone.utc)
    acumuladas = _distancias_acumuladas(ruta)
    metros_por_s = velocidad_kmh / 3.6
    ultimo = int(np.ceil(duracion_s)) + margen_s
    puntos = []
    for s in range(-margen_s, ultimo + 1):
        lat, lon = posicion_en_ruta(ruta, acumuladas, max(0.0, s * metros_por_s))
        puntos.append((inicio_utc + timedelta(seconds=s), lat, lon))
    return puntos


def escribir_gpx(puntos: Sequence[tuple[datetime, float, float]], ruta: Path) -> Path:
    gpx = gpxpy.gpx.GPX()
    gpx.name = "TapaHuecos - recorrido simulado (demo)"
    gpx.description = "Recorrido de demostración por la Avenida Primera de Montería; no es un registro real."
    pista = gpxpy.gpx.GPXTrack(name="Demo Avenida Primera")
    segmento = gpxpy.gpx.GPXTrackSegment()
    for instante, lat, lon in puntos:
        segmento.points.append(
            gpxpy.gpx.GPXTrackPoint(round(lat, 7), round(lon, 7), time=instante)
        )
    pista.segments.append(segmento)
    gpx.tracks.append(pista)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(gpx.to_xml())
    return ruta


# --- Nombres y argumentos ----------------------------------------------------------------


def nombre_video(inicio_local: datetime) -> str:
    return inicio_local.strftime("VID_%Y%m%d_%H%M%S.mp4")


def resolver_inicio_local(texto: str | None, utc_offset_horas: float) -> datetime:
    """Hora local (con zona) de inicio: la indicada o la actual redondeada al segundo."""
    zona = timezone(timedelta(hours=utc_offset_horas))
    if texto:
        return interpretar_fecha(texto, utc_offset_horas).astimezone(zona)
    ahora = datetime.now(zona)
    return (ahora + timedelta(microseconds=500_000)).replace(microsecond=0)


def _tamano(texto: str) -> tuple[int, int]:
    try:
        ancho, alto = (int(v) for v in texto.lower().split("x"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("use ANCHOxALTO, por ejemplo 1280x720") from error
    if ancho < 16 or alto < 16:
        raise argparse.ArgumentTypeError("el tamaño mínimo es 16x16")
    return ancho, alto


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--imagenes", type=Path, required=True,
                   help="carpeta con imágenes (.jpg, .jpeg, .png), p. ej. datos/rdd_yolo/images/test")
    p.add_argument("--destino", type=Path, default=Path("datos/demo"))
    p.add_argument("--cantidad", type=int, default=20, help="número de imágenes del video")
    p.add_argument("--segundos-por-imagen", type=float, default=2.0)
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--tamano", type=_tamano, default=(1280, 720), metavar="ANCHOxALTO")
    p.add_argument("--separacion", type=int, default=3,
                   help="fotogramas negros entre imágenes (para que el seguidor cierre la pista)")
    p.add_argument("--inicio", help="hora local de inicio, ISO 8601 (por defecto, ahora)")
    p.add_argument("--utc-offset", type=float, default=-5.0, help="horas respecto a UTC (Colombia: -5)")
    p.add_argument("--velocidad", type=float, default=20.0, help="velocidad simulada en km/h")
    p.add_argument("--semilla", type=int, default=None)
    args = p.parse_args(argv)

    if args.cantidad < 1 or args.fps <= 0 or args.segundos_por_imagen <= 0 or args.velocidad <= 0:
        p.error("--cantidad, --fps, --segundos-por-imagen y --velocidad deben ser positivos")
    if not args.imagenes.is_dir():
        p.error(f"no existe la carpeta {args.imagenes}")

    por_imagen = fotogramas_por_imagen(args.segundos_por_imagen, args.fps)
    if por_imagen // CADA_N_FOTOGRAMAS < MIN_FOTOGRAMAS:
        print(
            f"Aviso: cada imagen dura {por_imagen} fotogramas; con cada_n_fotogramas="
            f"{CADA_N_FOTOGRAMAS} y min_fotogramas={MIN_FOTOGRAMAS} puede que no se registre "
            "ningún daño. Suba --segundos-por-imagen o --fps."
        )

    azar = random.Random(args.semilla)
    imagenes = seleccionar_imagenes(args.imagenes, args.cantidad, azar)
    etiquetas = carpeta_etiquetas(args.imagenes)
    if etiquetas is not None:
        huecos = sum(INDICE_HUECO in clases_etiquetadas(etiquetas / f"{i.stem}.txt") for i in imagenes)
        print(f"{len(imagenes)} imágenes elegidas ({huecos} con huecos D40), etiquetas en {etiquetas}")
    else:
        print(f"{len(imagenes)} imágenes elegidas al azar (no se encontraron etiquetas YOLO)")

    inicio = resolver_inicio_local(args.inicio, args.utc_offset)
    ancho, alto = args.tamano
    ruta_video = args.destino / nombre_video(inicio)
    n = escribir_video(imagenes, ruta_video, ancho, alto, args.fps, args.segundos_por_imagen,
                       args.separacion)
    if n == 0:
        print("No se pudo leer ninguna imagen.")
        return 1
    duracion = n / args.fps

    ruta_gpx = ruta_video.with_name(f"{ruta_video.stem}_demo.gpx")
    puntos = puntos_gpx(inicio, duracion, args.velocidad)
    escribir_gpx(puntos, ruta_gpx)

    print(
        f"\nVideo: {ruta_video} ({n} fotogramas, {duracion:.1f} s, {ancho}x{alto} a {args.fps:g} fps)\n"
        f"GPX  : {ruta_gpx} ({len(puntos)} puntos, Avenida Primera de Montería a {args.velocidad:g} km/h)\n"
        f"Inicio: {inicio.isoformat()} (hora local)\n"
        "\nPara procesarlo:\n\n"
        f"  tapahuecos procesar --video {ruta_video.as_posix()} --gpx {ruta_gpx.as_posix()} "
        "--pesos modelos/best_rdd.pt --salida salidas/demo\n"
        "\nRecuerde: son datos de DEMOSTRACIÓN. Las imágenes no son de Montería y el recorrido "
        "GPS es simulado; los resultados no son de campo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
