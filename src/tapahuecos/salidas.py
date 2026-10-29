"""Etapa 6: video anotado, mapa HTML, CSV y resumen."""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path

import cv2
import numpy as np

from tapahuecos.clases import clase_por_codigo
from tapahuecos.detector import Deteccion

log = logging.getLogger(__name__)

MONTERIA = (8.7479, -75.8814)
_FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def _texto_con_fondo(imagen: np.ndarray, texto: str, origen: tuple[int, int], color) -> None:
    (ancho, alto), base = cv2.getTextSize(texto, _FUENTE, 0.5, 1)
    x, y = origen
    y = max(y, alto + base + 2)
    cv2.rectangle(imagen, (x, y - alto - base - 2), (x + ancho + 4, y), color, cv2.FILLED)
    cv2.putText(imagen, texto, (x + 2, y - base), _FUENTE, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def dibujar_deteccion(
    imagen: np.ndarray,
    det: Deteccion,
    mascara: np.ndarray | None = None,
    area_m2: float | None = None,
) -> None:
    """Superpone sobre el fotograma la máscara semitransparente, el recuadro y la etiqueta."""
    x1, y1, x2, y2 = det.caja
    color = det.clase.color_bgr
    if mascara is not None and mascara.any():
        region = imagen[y1:y2, x1:x2]
        capa = region.copy()
        capa[mascara > 0] = color
        cv2.addWeighted(capa, 0.45, region, 0.55, 0, dst=region)
    cv2.rectangle(imagen, (x1, y1), (x2, y2), color, 2)
    partes = [det.clase.codigo, f"{det.confianza:.2f}"]
    if det.track_id is not None:
        partes.insert(1, f"#{det.track_id}")
    if area_m2 is not None:
        partes.append(f"{area_m2:.2f} m2")
    _texto_con_fondo(imagen, " ".join(partes), (x1, y1), color)


def dibujar_cabecera(imagen: np.ndarray, texto: str) -> None:
    _texto_con_fondo(imagen, texto, (8, 24), (40, 40, 40))


class EscritorVideo:
    """VideoWriter que se abre con el tamaño del primer fotograma recibido."""

    def __init__(self, ruta: Path, fps: float):
        self.ruta = Path(ruta)
        self.fps = fps
        self._escritor: cv2.VideoWriter | None = None

    def escribir(self, imagen: np.ndarray) -> None:
        if self._escritor is None:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            alto, ancho = imagen.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._escritor = cv2.VideoWriter(str(self.ruta), fourcc, self.fps, (ancho, alto))
        self._escritor.write(imagen)

    def cerrar(self) -> None:
        if self._escritor is not None:
            self._escritor.release()


def _popup(fila: dict, ruta_imagen: str) -> str:
    area = f"{fila['area_m2']:.3f} m²" if fila["area_m2"] is not None else f"{fila['area_px']} px"
    verificado = {None: "sin revisar", 1: "real", 0: "falso positivo"}[fila["verificado"]]
    registros = fila.get("registros", 1)
    return (
        f"<b>{html.escape(fila['clase'])} – {html.escape(fila['nombre_clase'])}</b><br>"
        + (f"Registrado en {registros} recorridos<br>" if registros > 1 else "")
        + f"Confianza: {fila['confianza']:.2f}<br>"
        f"Área aprox.: {area}<br>"
        f"Hora (UTC): {html.escape(fila['instante_utc'] or '—')}<br>"
        f"Video: {html.escape(Path(fila['video']).name)} @ {fila['tiempo_video_s']:.1f} s<br>"
        f"Revisión: {verificado}<br>"
        f'<img src="{html.escape(ruta_imagen)}" width="240">'
    )


def generar_mapa(filas: list[dict], ruta_html: Path, carpeta_base: Path) -> Path:
    """Mapa interactivo con una capa por tipo de daño. `carpeta_base` es donde está la BD."""
    import folium

    ruta_html = Path(ruta_html)
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    con_gps = [f for f in filas if f["latitud"] is not None and f["longitud"] is not None]
    if len(con_gps) < len(filas):
        log.warning("%d daños sin coordenada no aparecen en el mapa.", len(filas) - len(con_gps))

    mapa = folium.Map(location=MONTERIA, zoom_start=14, tiles="OpenStreetMap")
    capas: dict[str, folium.FeatureGroup] = {}
    for fila in con_gps:
        clase = clase_por_codigo(fila["clase"])
        if clase.codigo not in capas:
            capas[clase.codigo] = folium.FeatureGroup(name=f"{clase.codigo} – {clase.nombre}")
        imagen = os.path.relpath(Path(carpeta_base) / fila["recorte"], ruta_html.parent)
        folium.CircleMarker(
            location=(fila["latitud"], fila["longitud"]),
            radius=7,
            color=clase.color_hex,
            fill=True,
            fill_opacity=0.85,
            tooltip=f"{clase.codigo} · {clase.nombre}",
            popup=folium.Popup(_popup(fila, Path(imagen).as_posix()), max_width=270),
        ).add_to(capas[clase.codigo])
    for codigo in sorted(capas):
        capas[codigo].add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    if con_gps:
        lats = [f["latitud"] for f in con_gps]
        lons = [f["longitud"] for f in con_gps]
        mapa.fit_bounds([(min(lats), min(lons)), (max(lats), max(lons))], max_zoom=18)
    mapa.save(str(ruta_html))
    return ruta_html


def exportar_csv(filas: list[dict], ruta: Path) -> Path:
    import pandas as pd

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig para que Excel muestre bien las tildes
    pd.DataFrame(filas).to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


def resumen(filas: list[dict]):
    """Tabla por clase: registros, daños únicos, área total y media, porcentaje con GPS y revisión."""
    import pandas as pd

    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    df["grupo_unico"] = df["grupo"].fillna(df["id"]) if "grupo" in df else df["id"]
    return (
        df.groupby(["clase", "nombre_clase"])
        .agg(
            cantidad=("id", "count"),
            unicos=("grupo_unico", "nunique"),
            area_total_m2=("area_m2", "sum"),
            area_media_m2=("area_m2", "mean"),
            con_gps=("latitud", lambda s: s.notna().mean()),
            revisados=("verificado", lambda s: s.notna().sum()),
            reales=("verificado", lambda s: (s == 1).sum()),
        )
        .round(4)
        .reset_index()
    )
