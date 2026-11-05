"""Etapa 3a: separar el daño dentro del recuadro de YOLO con OpenCV.

Recorte → escala de grises → realce → umbral → morfología → contornos → máscara binaria.

El umbral depende del tipo de daño:
- Huecos (D40): región compacta en el centro del recuadro → CLAHE, suavizado y umbral de
  Otsu. La polaridad se decide comparando el centro con el borde: el hueco puede ser más
  oscuro que el asfalto (agujero, sombra) o más claro (base expuesta, polvo, agua que
  refleja el cielo). Se conservan solo las regiones que tocan el centro del recuadro.
- Grietas (D00, D10): líneas finas → transformación black-hat, que resalta estructuras
  más oscuras y delgadas que el elemento estructurante. El umbral es por histéresis sobre
  percentiles de la respuesta: semillas en lo más fuerte, que crecen por los píxeles
  vecinos algo más débiles. Otsu no sirve aquí: la respuesta es casi siempre ruido con un
  solo pico y la partiría por la mitad. Se conservan solo los grupos alargados.
- Piel de cocodrilo (D20): black-hat y Otsu, más un cierre grande que une la malla en una
  sola región.

En grietas y piel de cocodrilo se recortan antes los brillos (marcas viales, reflejos):
si no, el asfalto junto a una línea pintada parece un valle oscuro.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from tapahuecos.config import ConfigSegmentacion

MODO_POR_CLASE = {"D00": "linea", "D10": "linea", "D20": "malla", "D40": "region"}


@dataclass
class Segmentacion:
    mascara: np.ndarray  # uint8, 255 = daño, mismo tamaño que el recorte
    contornos: list[np.ndarray]  # en coordenadas del recorte

    @property
    def area_px(self) -> int:
        return int(cv2.countNonZero(self.mascara))


def _impar(n: int) -> int:
    n = max(int(n), 1)
    return n if n % 2 else n + 1


def _elipse(tamano: int) -> np.ndarray:
    tamano = _impar(tamano)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tamano, tamano))


def realzar(gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    """Mejora de la imagen: ecualización adaptativa (CLAHE) y suavizado gaussiano.

    En recortes pequeños la rejilla se reduce para que cada tesela mida al menos
    `clahe_tesela_min_px`: con teselas de pocos píxeles CLAHE solo amplifica ruido.
    """
    rejilla = min(cfg.clahe_rejilla, min(gris.shape[:2]) // max(1, cfg.clahe_tesela_min_px))
    rejilla = max(1, rejilla)
    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_limite, tileGridSize=(rejilla, rejilla))
    k = _impar(cfg.kernel_suavizado)
    return cv2.GaussianBlur(clahe.apply(gris), (k, k), 0)


def _zona_central(alto: int, ancho: int, fraccion: float) -> tuple[slice, slice]:
    my = round(alto * (1 - fraccion) / 2)
    mx = round(ancho * (1 - fraccion) / 2)
    return slice(my, max(my + 1, alto - my)), slice(mx, max(mx + 1, ancho - mx))


def _regiones_centrales(binaria: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    """Deja solo las regiones que tocan el centro del recuadro: YOLO encuadra el hueco."""
    _, etiquetas = cv2.connectedComponents(binaria)
    fy, fx = _zona_central(*binaria.shape[:2], cfg.fraccion_centro)
    centrales = np.unique(etiquetas[fy, fx])
    return np.where(np.isin(etiquetas, centrales[centrales > 0]), 255, 0).astype(np.uint8)


def _centralidad(mascara: np.ndarray, cfg: ConfigSegmentacion) -> float:
    """Fracción del centro cubierta menos fracción del borde cubierta: alta para un hueco bien encuadrado."""
    fy, fx = _zona_central(*mascara.shape[:2], cfg.fraccion_centro)
    dentro = mascara > 0
    centro = dentro[fy, fx]
    borde = dentro.sum() - centro.sum()
    area_borde = dentro.size - centro.size
    return float(centro.mean()) - (borde / area_borde if area_borde else 0.0)


def _region(gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    suave = realzar(gris, cfg)
    # En recortes pequeños la limpieza no puede ser del tamaño del propio hueco.
    limpieza = _elipse(min(cfg.kernel_morfologico, max(1, min(gris.shape[:2]) // 8)))
    candidatas = []
    # El hueco puede ser más oscuro que el asfalto (agujero, sombra) o más claro (base
    # expuesta, polvo, agua que refleja el cielo): se prueban las dos polaridades de Otsu.
    for tipo in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        _, binaria = cv2.threshold(suave, 0, 255, tipo | cv2.THRESH_OTSU)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, limpieza)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, limpieza)
        candidatas.append(_regiones_centrales(binaria, cfg))
    # Ante un empate gana la oscura (la primera), el caso habitual.
    return max(candidatas, key=lambda m: _centralidad(m, cfg))


def _black_hat(suave: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    tope = np.percentile(suave, cfg.percentil_tope_brillo)
    recortada = np.minimum(suave, tope).astype(np.uint8)
    return cv2.morphologyEx(recortada, cv2.MORPH_BLACKHAT, _elipse(cfg.kernel_grietas))


def _es_alargado(contorno: np.ndarray, cfg: ConfigSegmentacion) -> bool:
    (_, _), (w, h), _ = cv2.minAreaRect(contorno)
    if max(w, h) / max(min(w, h), 1.0) >= cfg.alargamiento_minimo:
        return True
    # Una grieta ramificada o curva no es alargada en su rectángulo, pero lo llena poco.
    return cv2.contourArea(contorno) / max(w * h, 1.0) <= cfg.llenado_maximo


def _lineas(gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    # Sin CLAHE: realza la textura del asfalto, que compite con las grietas finas. El
    # suavizado es mínimo para no borrar grietas de 1 o 2 píxeles.
    realce = _black_hat(cv2.GaussianBlur(gris, (3, 3), 0), cfg)
    debil = realce > max(np.percentile(realce, cfg.percentil_crecimiento), cfg.realce_minimo / 2)
    fuerte = realce > max(np.percentile(realce, cfg.percentil_semilla), cfg.realce_minimo)
    _, etiquetas = cv2.connectedComponents(debil.astype(np.uint8), connectivity=8)
    semillas = np.unique(etiquetas[fuerte])
    binaria = np.where(np.isin(etiquetas, semillas[semillas > 0]), 255, 0).astype(np.uint8)

    # Los tramos de una grieta punteada se agrupan antes de juzgar su forma.
    grupos, _ = cv2.findContours(
        cv2.dilate(binaria, _elipse(cfg.union_grietas_px)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    grupos = [g for g in grupos if cv2.contourArea(g) >= cfg.area_minima_px and _es_alargado(g, cfg)]
    validos = np.zeros_like(binaria)
    cv2.drawContours(validos, grupos, -1, 255, cv2.FILLED)
    return cv2.morphologyEx(binaria & validos, cv2.MORPH_CLOSE, _elipse(3))


def _malla(gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    realce = _black_hat(realzar(gris, cfg), cfg)
    _, binaria = cv2.threshold(realce, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, _elipse(cfg.kernel_morfologico))
    return cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, _elipse(cfg.kernel_grietas))


def segmentar(recorte: np.ndarray, codigo_clase: str, cfg: ConfigSegmentacion) -> Segmentacion:
    alto, ancho = recorte.shape[:2]
    vacia = np.zeros((alto, ancho), np.uint8)
    modo = MODO_POR_CLASE.get(codigo_clase)
    # Las clases que no son daños (p. ej. "person" de un modelo genérico) no se segmentan.
    if modo is None or alto < 3 or ancho < 3:
        return Segmentacion(vacia, [])

    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY) if recorte.ndim == 3 else recorte
    if float(gris.std()) < cfg.contraste_minimo:
        return Segmentacion(vacia, [])  # superficie uniforme: el umbral solo separaría ruido

    if modo == "region":
        binaria = _region(gris, cfg)
    elif modo == "linea":
        binaria = _lineas(gris, cfg)
    else:
        binaria = _malla(gris, cfg)

    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # En grietas el área mínima ya se exigió a cada grupo de tramos, no a cada tramo suelto.
    if modo != "linea":
        contornos = [c for c in contornos if cv2.contourArea(c) >= cfg.area_minima_px]
    mascara = vacia
    if contornos:
        cv2.drawContours(mascara, contornos, -1, 255, cv2.FILLED)
    return Segmentacion(mascara, contornos)
