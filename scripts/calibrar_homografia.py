"""Calibra la homografía cámara → vía para convertir el área de píxeles a m².

1. Con la cámara ya montada en el vehículo (en la misma posición que usará siempre),
   grabe o fotografíe un tramo de vía con un rectángulo de medidas conocidas en el
   suelo: marcas viales, baldosas, o cuatro objetos colocados con cinta métrica.
2. Ejecute este script y haga clic en las 4 esquinas de ese rectángulo en el orden:
   inferior-izquierda, inferior-derecha, superior-derecha, superior-izquierda.
3. Teclas: [s] guardar · [r] reiniciar puntos · [q] salir sin guardar.

Uso:
    python scripts/calibrar_homografia.py --video datos/videos/calibracion.mp4 --segundo 3 \
        --ancho 3.0 --largo 5.0
    python scripts/calibrar_homografia.py --imagen foto.jpg --ancho 3 --largo 5 \
        --puntos "412,690;905,688;780,455;520,457"     # sin ventana

Se guardan calibracion/homografia.npy y una vista cenital para comprobar el resultado:
si el rectángulo se ve rectangular y con sus proporciones reales, la calibración es buena.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

PIXELES_POR_METRO_VISTA = 100
ORDEN = ["inferior-izquierda", "inferior-derecha", "superior-derecha", "superior-izquierda"]
# Igual que video.rotacion: grados en sentido horario → código de cv2.rotate
ROTACIONES = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def cargar_imagen(args: argparse.Namespace) -> np.ndarray:
    if args.imagen:
        imagen = cv2.imread(str(args.imagen))
    else:
        cap = cv2.VideoCapture(str(args.video))
        cap.set(cv2.CAP_PROP_POS_MSEC, args.segundo * 1000)
        _, imagen = cap.read()
        cap.release()
    if imagen is None:
        raise SystemExit("No se pudo leer la imagen o el fotograma indicado.")
    if args.rotacion:
        imagen = cv2.rotate(imagen, ROTACIONES[args.rotacion])
    return imagen


def elegir_puntos(imagen: np.ndarray) -> list[tuple[int, int]] | None:
    puntos: list[tuple[int, int]] = []
    ventana = "Calibracion: clic en 4 esquinas (s guardar, r reiniciar, q salir)"

    def al_hacer_clic(evento, x, y, *_):
        if evento == cv2.EVENT_LBUTTONDOWN and len(puntos) < 4:
            puntos.append((x, y))

    cv2.namedWindow(ventana, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(ventana, al_hacer_clic)
    while True:
        vista = imagen.copy()
        for i, punto in enumerate(puntos):
            cv2.circle(vista, punto, 6, (0, 0, 255), -1)
            cv2.putText(vista, str(i + 1), (punto[0] + 8, punto[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        if len(puntos) > 1:
            cv2.polylines(vista, [np.array(puntos)], len(puntos) == 4, (0, 255, 255), 2)
        siguiente = ORDEN[len(puntos)] if len(puntos) < 4 else "listo: pulse s"
        cv2.putText(vista, f"Siguiente: {siguiente}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow(ventana, vista)
        tecla = cv2.waitKey(20) & 0xFF
        if tecla == ord("r"):
            puntos.clear()
        elif tecla == ord("s") and len(puntos) == 4:
            cv2.destroyAllWindows()
            return puntos
        elif tecla == ord("q"):
            cv2.destroyAllWindows()
            return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    fuente = p.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--video", type=Path)
    fuente.add_argument("--imagen", type=Path)
    p.add_argument("--segundo", type=float, default=0.0, help="instante del video a usar")
    p.add_argument("--ancho", type=float, required=True, help="ancho real del rectángulo (m)")
    p.add_argument("--largo", type=float, required=True,
                   help="largo real del rectángulo en el sentido de la vía (m)")
    p.add_argument("--rotacion", type=int, default=0, choices=[0, 90, 180, 270],
                   help="giro en sentido horario; use el mismo valor de video.rotacion")
    p.add_argument("--puntos", help="'x1,y1;x2,y2;x3,y3;x4,y4' para no abrir ventana")
    p.add_argument("--salida", type=Path, default=Path("calibracion/homografia.npy"))
    args = p.parse_args()

    imagen = cargar_imagen(args)
    if args.puntos:
        puntos = [tuple(map(float, par.split(","))) for par in args.puntos.split(";")]
        if len(puntos) != 4:
            p.error("--puntos necesita exactamente 4 pares x,y")
    else:
        puntos = elegir_puntos(imagen)
        if puntos is None:
            print("Calibración cancelada.")
            return

    origen = np.array(puntos, dtype=np.float32)
    # Coordenadas del suelo en metros, con el origen en la esquina inferior izquierda.
    destino = np.array(
        [[0, 0], [args.ancho, 0], [args.ancho, args.largo], [0, args.largo]], dtype=np.float32
    )
    homografia = cv2.getPerspectiveTransform(origen, destino)

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.salida, homografia)

    # Vista cenital: metros → píxeles de la vista, con el eje y hacia abajo.
    escala = PIXELES_POR_METRO_VISTA
    margen = 2.0
    ancho_vista = int((args.ancho + 2 * margen) * escala)
    alto_vista = int((args.largo + 2 * margen) * escala)
    a_vista = np.array(
        [[escala, 0, margen * escala], [0, -escala, alto_vista - margen * escala], [0, 0, 1]]
    )
    cenital = cv2.warpPerspective(imagen, a_vista @ homografia, (ancho_vista, alto_vista))
    ruta_vista = args.salida.with_name("vista_cenital.jpg")
    cv2.imwrite(str(ruta_vista), cenital)

    area_px = cv2.contourArea(origen)
    print(f"Homografía guardada en {args.salida}")
    print(f"Comprobación: el rectángulo mide {area_px:.0f} px² en la imagen = "
          f"{args.ancho * args.largo:.2f} m² en la vía. Revise {ruta_vista}.")


if __name__ == "__main__":
    main()
