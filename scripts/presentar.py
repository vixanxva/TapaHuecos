"""Demostración de la sustentación en un solo comando.

Sigue el orden del guion (docs/presentacion.md):

  mapa        abre el mapa de la campaña de Montería (48 daños revisados a mano)
  vivo        corre el pipeline completo sobre un video con GPX, con la detección en pantalla,
              y abre el mapa que genera
  resultados  imprime la precisión de campo por clase, calculada de la base revisada
  video       plan B: abre el video anotado de la campaña

Sin argumento hace mapa, vivo y resultados, con Enter entre uno y otro.

Uso:
    python scripts/presentar.py
    python scripts/presentar.py vivo
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from tapahuecos import cli  # noqa: E402
from tapahuecos.evaluacion import evaluar_campo  # noqa: E402
from tapahuecos.registro import BaseDatos  # noqa: E402

CAMPANA = RAIZ / "salidas" / "campana_20261108"
VIDEO_DEMO = RAIZ / "datos" / "demo" / "VID_20261104_210159.mp4"
GPX_DEMO = RAIZ / "datos" / "demo" / "VID_20261104_210159_demo.gpx"
PESOS = RAIZ / "modelos" / "best_rdd.pt"
SALIDA_VIVO = RAIZ / "salidas" / "en_vivo"

NECESITA = {
    "mapa": [CAMPANA / "mapa.html", CAMPANA / "danos.db"],
    "vivo": [VIDEO_DEMO, GPX_DEMO, PESOS],
    "resultados": [CAMPANA / "danos.db"],
    "video": [CAMPANA],
}
ORDEN = ["mapa", "vivo", "resultados"]


def abrir(ruta: Path) -> None:
    if ruta.suffix == ".html":
        webbrowser.open(ruta.as_uri())
    elif sys.platform == "win32":
        os.startfile(ruta)  # noqa: S606 - abre con el programa predeterminado de Windows
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)], check=False)


def titulo(texto: str) -> None:
    print(f"\n=== {texto} ===\n")


def paso_mapa() -> None:
    titulo("Mapa de la campaña · Montería, 8 de noviembre de 2026")
    with BaseDatos(CAMPANA / "danos.db") as bd:
        filas = bd.danos()
    recorridos = len({f["recorrido_id"] for f in filas})
    con_gps = sum(f["latitud"] is not None for f in filas)
    print(f"{len(filas)} daños de {recorridos} recorridos reales, {con_gps} con coordenada GPS.")
    print("Clic en un punto para ver el recorte del daño. Las calles necesitan internet.")
    abrir(CAMPANA / "mapa.html")


def paso_vivo() -> int:
    titulo("Detección en vivo: video + GPX -> recortes, base de datos y mapa")
    print("Video de demostración con imágenes de RDD2022 y un recorrido GPS simulado por la")
    print("Avenida Primera. Tarda alrededor de un minuto en CPU; [q] en la ventana lo detiene.\n")
    if SALIDA_VIVO.exists():
        shutil.rmtree(SALIDA_VIVO)  # cada corrida empieza limpia: el mapa no acumula corridas viejas
    codigo = cli.main([
        "procesar",
        "--video", str(VIDEO_DEMO),
        "--gpx", str(GPX_DEMO),
        "--pesos", str(PESOS),
        "--salida", str(SALIDA_VIVO),
        "--mostrar",
    ])
    if codigo == 0 and (SALIDA_VIVO / "mapa.html").exists():
        abrir(SALIDA_VIVO / "mapa.html")
    return codigo


def paso_resultados() -> None:
    titulo("Resultados de campo · revisión manual de cada daño registrado")
    with BaseDatos(CAMPANA / "danos.db") as bd:
        filas = bd.danos()

    print(f"{'Clase':<6}{'Tipo':<24}{'Detectados':>11}{'Reales':>8}{'Falsos':>8}{'Precisión':>11}")
    for clase in sorted({f["clase"] for f in filas}):
        grupo = [f for f in filas if f["clase"] == clase]
        revisados = [f for f in grupo if f["verificado"] is not None]
        reales = sum(f["verificado"] == 1 for f in revisados)
        precision = f"{reales / len(revisados):.2f}" if revisados else "-"
        print(f"{clase:<6}{grupo[0]['nombre_clase']:<24}{len(grupo):>11}{reales:>8}"
              f"{len(revisados) - reales:>8}{precision:>11}")

    m = evaluar_campo(filas)
    sin_revisar = len(filas) - m.revisados
    print("-" * 68)
    print(f"{'Total':<30}{len(filas):>11}{m.reales:>8}{m.revisados - m.reales:>8}"
          f"{m.precision if m.precision is not None else '-':>11}")
    if sin_revisar:
        print(f"\n{sin_revisar} daños sin revisar no cuentan en la precisión.")
    print("\nExhaustividad: sin medir (requiere recorrer la calle a pie y anotar cada daño).")


def paso_video() -> None:
    titulo("Plan B: video anotado de la campaña")
    videos = sorted(CAMPANA.glob("*_anotado.mp4"))
    if not videos:
        print(f"No hay videos anotados en {CAMPANA}")
        return
    print(videos[0].name)
    abrir(videos[0])


PASOS = {"mapa": paso_mapa, "vivo": paso_vivo, "resultados": paso_resultados, "video": paso_video}


def main() -> int:
    p = argparse.ArgumentParser(description="Demostración de la sustentación de TapaHuecos.")
    p.add_argument("paso", nargs="?", choices=list(PASOS), help="un solo paso (por defecto: todos)")
    args = p.parse_args()
    pasos = [args.paso] if args.paso else ORDEN

    faltan = sorted({r for paso in pasos for r in NECESITA[paso] if not r.exists()})
    if faltan:
        print("Faltan estos archivos:")
        for ruta in faltan:
            print(f"  {ruta.relative_to(RAIZ)}")
        return 1

    os.chdir(RAIZ)  # config.yaml y las rutas relativas de la configuración se leen desde aquí
    for i, paso in enumerate(pasos):
        if i:
            try:
                input("\n[Enter] siguiente paso · [Ctrl+C] salir ")
            except (KeyboardInterrupt, EOFError):
                print()
                return 0
        if PASOS[paso]() not in (None, 0):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
