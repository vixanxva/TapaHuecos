"""Etapa 2: detección con YOLO y seguimiento con ByteTrack (ambos de Ultralytics)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tapahuecos.clases import ClaseDano, clase_por_codigo
from tapahuecos.config import ConfigModelo


@dataclass
class Deteccion:
    caja: tuple[int, int, int, int]  # x1, y1, x2, y2 en píxeles
    clase: ClaseDano
    confianza: float
    track_id: int | None  # None mientras el seguidor no confirma el objeto


class Detector:
    def __init__(self, cfg: ConfigModelo):
        # Importación diferida: Ultralytics es pesado y las pruebas no lo necesitan.
        from ultralytics import YOLO

        pesos = Path(cfg.pesos)
        if pesos.parent != Path(".") and not pesos.exists():
            raise FileNotFoundError(
                f"No existe el modelo {pesos}. Entrénelo con scripts/entrenar.py "
                "o indique otro archivo con --pesos."
            )
        self.cfg = cfg
        self.modelo = YOLO(str(pesos))
        self._clases = {int(i): clase_por_codigo(n) for i, n in self.modelo.names.items()}

    def rastrear(self, imagen: np.ndarray) -> list[Deteccion]:
        """Detecta daños en un fotograma manteniendo el ID de cada uno entre fotogramas."""
        resultado = self.modelo.track(
            imagen,
            persist=True,
            tracker=self.cfg.tracker,
            conf=self.cfg.confianza,
            iou=self.cfg.iou,
            imgsz=self.cfg.tamano_imagen,
            device=self.cfg.dispositivo,
            verbose=False,
        )[0]
        cajas = resultado.boxes
        if cajas is None or len(cajas) == 0:
            return []
        xyxy = cajas.xyxy.cpu().numpy().round().astype(int)
        clases = cajas.cls.cpu().numpy().astype(int)
        confianzas = cajas.conf.cpu().numpy()
        ids = cajas.id.cpu().numpy().astype(int).tolist() if cajas.id is not None else None
        return [
            Deteccion(
                caja=tuple(xyxy[i]),
                clase=self._clases[clases[i]],
                confianza=float(confianzas[i]),
                track_id=ids[i] if ids is not None else None,
            )
            for i in range(len(xyxy))
        ]
