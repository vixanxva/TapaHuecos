"""Entrena (o ajusta) el detector YOLO. Pensado para Google Colab con GPU T4.

Fase 1, sobre RDD2022:
    python scripts/entrenar.py --datos datos/rdd_yolo/data.yaml --modelo yolov8s.pt \
        --nombre rdd --destino modelos/best_rdd.pt

Fase 2, ajuste fino con las fotos de Montería (más una parte de RDD2022):
    python scripts/entrenar.py --datos datos/combinado/data.yaml --modelo modelos/best_rdd.pt \
        --epocas 50 --nombre monteria --destino modelos/best.pt
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--datos", required=True, help="data.yaml del dataset")
    p.add_argument("--modelo", default="yolov8s.pt",
                   help="pesos iniciales: yolov8n/s.pt, yolo11n/s.pt o un .pt propio")
    p.add_argument("--epocas", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--lote", type=int, default=16, help="batch; -1 = automático según la GPU")
    p.add_argument("--paciencia", type=int, default=20, help="épocas sin mejora antes de parar")
    p.add_argument("--dispositivo", default=None, help="'0' para la GPU, 'cpu'")
    p.add_argument("--proyecto", default="runs/entrenamiento")
    p.add_argument("--nombre", default="tapahuecos")
    p.add_argument("--destino", type=Path, default=Path("modelos/best.pt"))
    args = p.parse_args()

    from ultralytics import YOLO

    modelo = YOLO(args.modelo)
    modelo.train(
        data=args.datos,
        epochs=args.epocas,
        imgsz=args.imgsz,
        batch=args.lote,
        patience=args.paciencia,
        device=args.dispositivo,
        project=args.proyecto,
        name=args.nombre,
        seed=42,
        # Las grietas tienen orientación con significado (D00 vs D10): se evita rotar,
        # pero el volteo horizontal es seguro.
        fliplr=0.5,
        degrees=0.0,
        plots=True,
    )
    mejor = Path(modelo.trainer.best)
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mejor, args.destino)
    print(f"Mejor modelo copiado a {args.destino} (curvas y matriz de confusión en {mejor.parents[1]})")


if __name__ == "__main__":
    main()
