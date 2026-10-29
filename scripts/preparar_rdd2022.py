"""Convierte RDD2022 (Pascal VOC) a formato YOLO con las cuatro clases del proyecto.

RDD2022 se descarga de:
https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547

Estructura esperada (una carpeta por país):
    RDD2022/<Pais>/train/images/*.jpg
    RDD2022/<Pais>/train/annotations/xmls/*.xml

Las particiones de prueba oficiales no traen etiquetas, por eso train/val/test
se generan a partir de la partición de entrenamiento.

Uso:
    python scripts/preparar_rdd2022.py --origen datos/RDD2022 --destino datos/rdd_yolo \
        --paises Japan India Czech Norway United_States China_MotorBike
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tapahuecos.clases import CODIGOS  # noqa: E402

INDICE = {codigo: i for i, codigo in enumerate(CODIGOS)}


def convertir_xml(ruta_xml: Path, ruta_imagen: Path) -> list[str]:
    """Devuelve las líneas YOLO (`clase cx cy w h`, normalizadas) de una anotación VOC."""
    raiz = ET.parse(ruta_xml).getroot()
    ancho = float(raiz.findtext("size/width") or 0)
    alto = float(raiz.findtext("size/height") or 0)
    if ancho <= 0 or alto <= 0:  # algunos XML traen tamaño 0
        imagen = cv2.imread(str(ruta_imagen))
        if imagen is None:
            return []
        alto, ancho = imagen.shape[:2]

    lineas = []
    for obj in raiz.iter("object"):
        nombre = (obj.findtext("name") or "").strip()
        if nombre not in INDICE:
            continue  # D43, D44, D50, Repair… quedan fuera del alcance
        caja = obj.find("bndbox")
        x1, y1, x2, y2 = (float(caja.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, x2 = sorted((max(0.0, min(x1, ancho)), max(0.0, min(x2, ancho))))
        y1, y2 = sorted((max(0.0, min(y1, alto)), max(0.0, min(y2, alto))))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        lineas.append(
            f"{INDICE[nombre]} {(x1 + x2) / 2 / ancho:.6f} {(y1 + y2) / 2 / alto:.6f} "
            f"{(x2 - x1) / ancho:.6f} {(y2 - y1) / alto:.6f}"
        )
    return lineas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--origen", type=Path, required=True, help="carpeta RDD2022 descomprimida")
    p.add_argument("--destino", type=Path, required=True)
    p.add_argument("--paises", nargs="*", help="subcarpetas a incluir (por defecto todas)")
    p.add_argument("--proporciones", nargs=3, type=float, default=(0.8, 0.1, 0.1),
                   metavar=("TRAIN", "VAL", "TEST"))
    p.add_argument("--vacias", type=float, default=0.1,
                   help="fracción de imágenes sin daños a conservar como negativos")
    p.add_argument("--semilla", type=int, default=42)
    args = p.parse_args()

    paises = args.paises or sorted(d.name for d in args.origen.iterdir() if d.is_dir())
    azar = random.Random(args.semilla)
    muestras: list[tuple[Path, list[str]]] = []
    for pais in paises:
        carpeta = args.origen / pais / "train"
        xmls = sorted((carpeta / "annotations" / "xmls").glob("*.xml"))
        if not xmls:
            print(f"Aviso: {carpeta} no tiene anotaciones; se omite.")
            continue
        conservadas = 0
        for ruta_xml in xmls:
            ruta_imagen = carpeta / "images" / f"{ruta_xml.stem}.jpg"
            if not ruta_imagen.exists():
                continue
            lineas = convertir_xml(ruta_xml, ruta_imagen)
            if lineas or azar.random() < args.vacias:
                muestras.append((ruta_imagen, lineas))
                conservadas += 1
        print(f"{pais}: {conservadas} imágenes")

    total = sum(args.proporciones)
    azar.shuffle(muestras)
    n_train = int(len(muestras) * args.proporciones[0] / total)
    n_val = int(len(muestras) * args.proporciones[1] / total)
    particiones = {
        "train": muestras[:n_train],
        "val": muestras[n_train:n_train + n_val],
        "test": muestras[n_train + n_val:],
    }

    conteo = {c: 0 for c in CODIGOS}
    for particion, elementos in particiones.items():
        (args.destino / "images" / particion).mkdir(parents=True, exist_ok=True)
        (args.destino / "labels" / particion).mkdir(parents=True, exist_ok=True)
        for ruta_imagen, lineas in elementos:
            # Prefijo con el país: los nombres de archivo se repiten entre países.
            nombre = f"{ruta_imagen.parents[2].name}_{ruta_imagen.stem}"
            shutil.copy2(ruta_imagen, args.destino / "images" / particion / f"{nombre}.jpg")
            (args.destino / "labels" / particion / f"{nombre}.txt").write_text(
                "\n".join(lineas), encoding="utf-8"
            )
            for linea in lineas:
                conteo[CODIGOS[int(linea.split()[0])]] += 1

    escribir_data_yaml(args.destino)
    print({k: len(v) for k, v in particiones.items()}, "| instancias:", conteo)


def escribir_data_yaml(destino: Path) -> Path:
    ruta = destino / "data.yaml"
    contenido = {
        "path": str(destino.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(CODIGOS)),
    }
    ruta.write_text(yaml.safe_dump(contenido, sort_keys=False, allow_unicode=True), "utf-8")
    return ruta


if __name__ == "__main__":
    main()
