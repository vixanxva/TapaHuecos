"""Une varios datasets YOLO (RDD2022 convertido, exportaciones de Roboflow con fotos
de Montería…) en uno solo, reordenando las clases por nombre a D00, D10, D20, D40.

Acepta las dos estructuras habituales:
    <dataset>/images/<split>/  y  <dataset>/labels/<split>/   (Ultralytics)
    <dataset>/<split>/images/  y  <dataset>/<split>/labels/   (Roboflow; "valid" = val)

Uso:
    python scripts/combinar_datasets.py --entradas datos/rdd_yolo datos/monteria_roboflow \
        --destino datos/combinado --repetir 1 3
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preparar_rdd2022 import escribir_data_yaml  # noqa: E402

from tapahuecos.clases import CODIGOS  # noqa: E402

SPLITS = {"train": "train", "val": "val", "valid": "val", "test": "test"}
EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def nombres_dataset(carpeta: Path) -> list[str]:
    datos = yaml.safe_load((carpeta / "data.yaml").read_text(encoding="utf-8"))
    nombres = datos["names"]
    if isinstance(nombres, dict):
        return [nombres[k] for k in sorted(nombres, key=int)]
    return list(nombres)


def carpetas_split(carpeta: Path, split: str) -> tuple[Path, Path] | None:
    for imagenes, etiquetas in (
        (carpeta / "images" / split, carpeta / "labels" / split),
        (carpeta / split / "images", carpeta / split / "labels"),
    ):
        if imagenes.is_dir():
            return imagenes, etiquetas
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--entradas", nargs="+", type=Path, required=True)
    p.add_argument("--destino", type=Path, required=True)
    p.add_argument("--repetir", nargs="*", type=int,
                   help="veces que se copia el train de cada entrada (sobremuestreo de datos locales)")
    args = p.parse_args()
    repetir = args.repetir or [1] * len(args.entradas)
    if len(repetir) != len(args.entradas):
        p.error("--repetir debe tener un valor por cada entrada")

    for entrada, veces in zip(args.entradas, repetir, strict=True):
        nombres = nombres_dataset(entrada)
        desconocidas = [n for n in nombres if n not in CODIGOS]
        if desconocidas:
            print(f"Aviso: {entrada.name} tiene clases fuera del proyecto que se descartan: "
                  f"{desconocidas}. Use exactamente {list(CODIGOS)} al etiquetar.")
        mapa = {i: CODIGOS.index(n) for i, n in enumerate(nombres) if n in CODIGOS}

        for split_origen, split in SPLITS.items():
            rutas = carpetas_split(entrada, split_origen)
            if rutas is None:
                continue
            imagenes, etiquetas = rutas
            (args.destino / "images" / split).mkdir(parents=True, exist_ok=True)
            (args.destino / "labels" / split).mkdir(parents=True, exist_ok=True)
            copias = veces if split == "train" else 1
            n = 0
            for imagen in sorted(imagenes.iterdir()):
                if imagen.suffix.lower() not in EXTENSIONES:
                    continue
                lineas = []
                etiqueta = etiquetas / f"{imagen.stem}.txt"
                if etiqueta.exists():
                    for linea in etiqueta.read_text(encoding="utf-8").splitlines():
                        partes = linea.split()
                        if partes and int(partes[0]) in mapa:
                            lineas.append(" ".join([str(mapa[int(partes[0])]), *partes[1:]]))
                for copia in range(copias):
                    nombre = f"{entrada.name}_{imagen.stem}" + (f"_r{copia}" if copia else "")
                    shutil.copy2(imagen, args.destino / "images" / split / f"{nombre}{imagen.suffix}")
                    (args.destino / "labels" / split / f"{nombre}.txt").write_text(
                        "\n".join(lineas), encoding="utf-8"
                    )
                n += 1
            print(f"{entrada.name}/{split_origen}: {n} imágenes (x{copias})")

    print("data.yaml:", escribir_data_yaml(args.destino))


if __name__ == "__main__":
    main()
