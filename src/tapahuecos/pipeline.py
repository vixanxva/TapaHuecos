"""Orquesta las seis etapas: entrada → YOLO → OpenCV → GPS → registro → salidas."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from tapahuecos.config import Config
from tapahuecos.detector import Deteccion
from tapahuecos.entrada import FuenteVideo, resolver_inicio
from tapahuecos.fusion import fusionar_bd, unicos
from tapahuecos.gps import Recorrido
from tapahuecos.medicion import Medidor
from tapahuecos.registro import BaseDatos, GestorDanos, Observacion
from tapahuecos.salidas import (
    EscritorVideo,
    dibujar_cabecera,
    dibujar_deteccion,
    exportar_csv,
    generar_mapa,
)
from tapahuecos.segmentacion import segmentar

log = logging.getLogger(__name__)


class DetectorProtocolo(Protocol):
    def rastrear(self, imagen: np.ndarray) -> list[Deteccion]: ...


@dataclass
class Resultado:
    recorrido_id: int
    fotogramas_procesados: int
    danos_registrados: int
    segundos: float
    video_anotado: Path
    base_datos: Path
    mapa: Path
    csv: Path

    @property
    def fps(self) -> float:
        return self.fotogramas_procesados / self.segundos if self.segundos else 0.0


def _verificar_solape(inicio: datetime, duracion_s: float, recorrido: Recorrido) -> None:
    fin = inicio + timedelta(seconds=duracion_s)
    if fin < recorrido.inicio or inicio > recorrido.fin:
        log.warning(
            "El video (%s → %s) no coincide en el tiempo con el GPX (%s → %s). "
            "Revise utc_offset_horas, desfase_gps_s o indique --inicio.",
            inicio.isoformat(timespec="seconds"), fin.isoformat(timespec="seconds"),
            recorrido.inicio.isoformat(timespec="seconds"),
            recorrido.fin.isoformat(timespec="seconds"),
        )


def procesar(
    origen: Path | int,
    cfg: Config,
    carpeta_salida: Path,
    ruta_gpx: Path | None = None,
    mostrar: bool = False,
    detector: DetectorProtocolo | None = None,
) -> Resultado:
    """Procesa un video (ruta) o una cámara (índice) y genera todas las salidas."""
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    recorrido = Recorrido.desde_gpx(ruta_gpx) if ruta_gpx else None
    medidor = Medidor.desde_config(cfg.calibracion)
    if detector is None:
        from tapahuecos.detector import Detector

        detector = Detector(cfg.modelo)

    cada_n = max(1, cfg.video.cada_n_fotogramas)
    ruta_bd = carpeta_salida / "danos.db"
    with BaseDatos(ruta_bd) as bd, FuenteVideo(origen) as fuente:
        inicio = None
        if not fuente.es_camara:
            inicio = resolver_inicio(
                Path(origen), cfg.video.inicio_grabacion, cfg.video.utc_offset_horas,
                fuente.duracion_s,
            )
            if inicio and recorrido:
                _verificar_solape(inicio, fuente.duracion_s, recorrido)

        recorrido_id = bd.nuevo_recorrido(
            "camara:" + str(origen) if fuente.es_camara else str(origen),
            str(ruta_gpx) if ruta_gpx else None,
            cfg.modelo.pesos,
        )
        gestor = GestorDanos(
            bd, recorrido_id, carpeta_salida / "recortes",
            cfg.registro.min_fotogramas, cfg.registro.max_ausencia,
        )
        nombre = f"camara{origen}" if fuente.es_camara else Path(origen).stem
        escritor = EscritorVideo(
            carpeta_salida / f"{nombre}_anotado.mp4", fuente.fps / cada_n
        )

        procesados = 0
        t0 = time.perf_counter()
        try:
            for fotograma in fuente.fotogramas(cada_n):
                if fuente.es_camara:
                    instante = datetime.now(timezone.utc)
                elif inicio is not None:
                    instante = inicio + timedelta(
                        seconds=fotograma.tiempo_s + cfg.video.desfase_gps_s
                    )
                else:
                    instante = None
                posicion = (
                    recorrido.posicion(instante, cfg.registro.tolerancia_gps_s)
                    if recorrido and instante
                    else None
                )

                imagen = fotograma.imagen
                anotado = imagen.copy()
                alto, ancho = imagen.shape[:2]
                for det in detector.rastrear(imagen):
                    x1, y1, x2, y2 = det.caja
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(ancho, x2), min(alto, y2)
                    if x2 - x1 < 3 or y2 - y1 < 3:
                        continue
                    det.caja = (x1, y1, x2, y2)
                    recorte = imagen[y1:y2, x1:x2]
                    seg = segmentar(recorte, det.clase.codigo, cfg.segmentacion)
                    area_m2 = medidor.area_m2([c + (x1, y1) for c in seg.contornos])
                    dibujar_deteccion(anotado, det, seg.mascara, area_m2)

                    if det.track_id is None:
                        continue
                    recorte_anotado = recorte.copy()
                    cv2.drawContours(recorte_anotado, seg.contornos, -1, det.clase.color_bgr, 2)
                    gestor.observar(
                        Observacion(
                            track_id=det.track_id,
                            clase=det.clase,
                            confianza=det.confianza,
                            fotograma=fotograma.indice,
                            tiempo_video_s=fotograma.tiempo_s,
                            instante_utc=instante,
                            latitud=posicion[0] if posicion else None,
                            longitud=posicion[1] if posicion else None,
                            area_px=seg.area_px,
                            area_m2=area_m2,
                            caja=det.caja,
                            recorte=recorte_anotado,
                        )
                    )
                gestor.cerrar_ausentes(fotograma.indice)

                procesados += 1
                gps = f"{posicion[0]:.5f}, {posicion[1]:.5f}" if posicion else "sin GPS"
                dibujar_cabecera(
                    anotado,
                    f"t={fotograma.tiempo_s:6.1f}s  {gps}  registrados={gestor.registrados}",
                )
                escritor.escribir(anotado)

                if fuente.total and procesados % 100 == 0:
                    log.info("%5.1f %% del video", 100 * fotograma.indice / fuente.total)
                if mostrar:
                    cv2.imshow("TapaHuecos (q para salir)", anotado)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            gestor.finalizar()
            escritor.cerrar()
            if mostrar:
                cv2.destroyAllWindows()
        segundos = time.perf_counter() - t0

        # El mapa y el CSV acumulan todos los recorridos de la carpeta. El mapa muestra
        # cada daño una vez aunque se haya registrado en varios recorridos.
        fusionar_bd(bd, cfg.registro.radio_fusion_m)
        todas = bd.danos()
        mapa = generar_mapa(unicos(todas), carpeta_salida / "mapa.html", carpeta_salida)
        csv = exportar_csv(todas, carpeta_salida / "danos.csv")

    return Resultado(
        recorrido_id=recorrido_id,
        fotogramas_procesados=procesados,
        danos_registrados=gestor.registrados,
        segundos=segundos,
        video_anotado=escritor.ruta,
        base_datos=ruta_bd,
        mapa=mapa,
        csv=csv,
    )
