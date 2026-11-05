"""Etapa 3a: separar el daño dentro del recuadro de YOLO con OpenCV.

Recorte → escala de grises → realce → umbral → morfología → contornos → máscara binaria.

El umbral depende del tipo de daño:
- Huecos (D40): región compacta en el centro del recuadro → CLAHE, suavizado y umbral de
  Otsu. La polaridad se decide comparando el centro con el borde: el hueco puede ser más
  oscuro que el asfalto (agujero, sombra) o más claro (base expuesta, polvo, agua que
  refleja el cielo). Se conservan solo las regiones que tocan el centro del recuadro.
  Otsu parte el recorte en dos mitades aunque el hueco sea pequeño: si la máscara invade
  las esquinas (que en un recuadro ajustado son asfalto) o apenas cubre el centro, se
  prueba otra máscara: lo que se aparta del asfalto de las esquinas en brillo, color y
  textura (rareza), con umbral por histéresis.
- Grietas (D00, D10): líneas finas → profundidad de valle (cuánto más oscuro es el píxel
  que sus dos lados en alguna orientación), en unidades de la textura del recorte. YOLO
  encuadra la grieta de punta a punta, así que se busca por programación dinámica el camino
  más oscuro a lo largo del eje largo del recuadro, y luego una posible rama lejos de él.
  Sus tramos con respuesta sostenida son la grieta; se rellenan los huecos cortos y se
  recupera el ancho con un crecimiento corto. Un umbral global no sirve: la grieta tenue
  queda por debajo de la textura gruesa del asfalto, que lo supera en manchas sueltas.
- Piel de cocodrilo (D20): la malla es una región, no una grieta. Se mide la DENSIDAD local
  de grietas (black-hat pequeño, normalizado por la iluminación local) y se umbraliza en
  relación con la densidad media del recuadro. Después se quitan la pintura limpia, las
  sombras que cubren una parte minoritaria del recuadro (oscuras y azuladas) y la vegetación.
  Se trabaja a un tamaño normalizado, así que los parámetros no dependen del recorte.

Las marcas viales (blancas o amarillas) se detectan en grietas y en piel de cocodrilo: si
no, el asfalto junto a una línea pintada parece un valle oscuro.
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


def _rellenar(binaria: np.ndarray) -> np.ndarray:
    """Rellena los agujeros interiores: un hueco con borde oscuro y fondo claro es un solo daño."""
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    llena = np.zeros_like(binaria)
    cv2.drawContours(llena, contornos, -1, 255, cv2.FILLED)
    return llena


def _nucleo_y_esquinas(alto: int, ancho: int) -> tuple[np.ndarray, np.ndarray]:
    """Núcleo: elipse de medio tamaño en el centro. Esquinas: fuera de la elipse inscrita.

    YOLO encuadra el hueco ajustado, así que el núcleo es casi siempre hueco y las
    esquinas, casi siempre asfalto (una elipse inscrita deja libre el 21 % del recuadro).
    """
    yy, xx = np.ogrid[0:alto, 0:ancho]
    r2 = ((yy + 0.5 - alto / 2) / (alto / 2)) ** 2 + ((xx + 0.5 - ancho / 2) / (ancho / 2)) ** 2
    return r2 <= 0.25, r2 > 1.0


# OpenCV arma las tablas de la conversión a Lab en la primera llamada (~100 ms): se hace al
# importar para que no caiga sobre el primer hueco del video.
cv2.cvtColor(np.zeros((1, 1, 3), np.uint8), cv2.COLOR_BGR2LAB)

# Desviación mínima de cada rasgo en el asfalto de referencia: en esquinas casi planas (o
# con el color en bloques del JPEG) la MAD sale cercana a cero y todo parecería raro.
_PISO_RASGO = {"L": 3.0, "a": 1.5, "b": 1.5, "T": 1.0}


def _rasgos_hueco(gris: np.ndarray, color: np.ndarray | None) -> dict[str, np.ndarray]:
    """Brillo, color (a*, b* de Lab) y textura suavizados a una escala relativa al recorte.

    El color separa la base expuesta o el barro del asfalto aunque brillen igual; la
    textura separa el agua o el polvo lisos del asfalto rugoso.
    """
    sigma = max(0.7, min(gris.shape[:2]) * 0.04)
    brillo = gris.astype(np.float32)
    rasgos = {"L": cv2.GaussianBlur(brillo, (0, 0), sigma)}
    if color is not None:
        lab = cv2.cvtColor(color, cv2.COLOR_BGR2LAB).astype(np.float32)
        rasgos["a"] = cv2.GaussianBlur(lab[..., 1], (0, 0), sigma)
        rasgos["b"] = cv2.GaussianBlur(lab[..., 2], (0, 0), sigma)
    detalle = np.abs(brillo - cv2.GaussianBlur(brillo, (0, 0), max(0.7, sigma / 2) + 0.8))
    rasgos["T"] = cv2.GaussianBlur(detalle, (0, 0), sigma * 1.5)
    return rasgos


def _desvio_del_plano(
    valores: np.ndarray, esquinas: np.ndarray, posicion: np.ndarray, piso: float
) -> np.ndarray:
    """Residuo normalizado respecto a un plano ajustado al asfalto de las esquinas.

    El plano absorbe los degradados de luz a lo ancho del recuadro; el ajuste se repite
    sin los píxeles atípicos por si el hueco llega a alguna esquina.
    """
    plano = valores.reshape(-1)
    y, a = plano[esquinas], posicion[esquinas]
    usar = np.ones(len(y), bool)
    for _ in range(2):
        coef = np.linalg.lstsq(a[usar], y[usar], rcond=None)[0]
        residuo = y - a @ coef
        mad = 1.4826 * float(np.median(np.abs(residuo[usar] - np.median(residuo[usar]))))
        nuevo = np.abs(residuo) < 2.5 * max(mad, piso)
        if nuevo.sum() < 8:
            break
        usar = nuevo
    residuo = y - a @ coef
    escala = max(1.4826 * float(np.median(np.abs(residuo[usar]))), piso)
    return ((plano - posicion @ coef) / escala).reshape(valores.shape)


def _rareza(gris: np.ndarray, color: np.ndarray | None, esquinas: np.ndarray) -> np.ndarray:
    """Cuánto se aparta cada píxel del asfalto de las esquinas, sumando brillo, color y textura.

    No depende de la polaridad: un hueco oscuro, uno claro o uno con borde oscuro y fondo
    claro se apartan igual del asfalto.
    """
    alto, ancho = gris.shape[:2]
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    posicion = np.stack([np.ones(alto * ancho, np.float32), xx.reshape(-1) / ancho, yy.reshape(-1) / alto], 1)
    cuadrado = np.zeros((alto, ancho), np.float32)
    for nombre, valores in _rasgos_hueco(gris, color).items():
        cuadrado += _desvio_del_plano(valores, esquinas.reshape(-1), posicion, _PISO_RASGO[nombre]) ** 2
    return np.sqrt(cuadrado)


def _mascara_rareza(
    rareza: np.ndarray, nucleo: np.ndarray, limpieza: np.ndarray, cfg: ConfigSegmentacion
) -> np.ndarray:
    """Histéresis sobre la rareza: semillas muy raras en el núcleo que crecen por lo algo raro.

    El umbral bajo sube con la rareza del propio hueco: si el hueco es muy distinto del
    asfalto, las zonas apenas distintas que lo rodean (sombras, polvo) no se le pegan.
    """
    pico = float(np.percentile(rareza[nucleo], 95))
    bajo = max(cfg.huecos_rareza_baja, cfg.huecos_rareza_relativa * pico)
    alto = max(cfg.huecos_rareza_alta, bajo)
    debil = np.where(rareza > bajo, 255, 0).astype(np.uint8)
    debil = cv2.morphologyEx(debil, cv2.MORPH_OPEN, limpieza)
    debil = cv2.morphologyEx(debil, cv2.MORPH_CLOSE, limpieza)
    _, etiquetas = cv2.connectedComponents(debil)
    semillas = np.unique(etiquetas[(rareza > alto) & nucleo])
    return _rellenar(np.where(np.isin(etiquetas, semillas[semillas > 0]), 255, 0).astype(np.uint8))


def _otsu_central(gris: np.ndarray, limpieza: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    suave = realzar(gris, cfg)
    candidatas = []
    # El hueco puede ser más oscuro que el asfalto (agujero, sombra) o más claro (base
    # expuesta, polvo, agua que refleja el cielo): se prueban las dos polaridades de Otsu.
    for tipo in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        _, binaria = cv2.threshold(suave, 0, 255, tipo | cv2.THRESH_OTSU)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, limpieza)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, limpieza)
        candidatas.append(_regiones_centrales(binaria, cfg))
    # Ante un empate gana la oscura (la primera), el caso habitual.
    return _rellenar(max(candidatas, key=lambda m: _centralidad(m, cfg)))


def _region(gris: np.ndarray, cfg: ConfigSegmentacion, color: np.ndarray | None = None) -> np.ndarray:
    alto, ancho = gris.shape[:2]
    # En recortes pequeños la limpieza no puede ser del tamaño del propio hueco.
    limpieza = _elipse(min(cfg.kernel_morfologico, max(1, min(alto, ancho) // 8)))
    otsu = _otsu_central(gris, limpieza, cfg)
    nucleo, esquinas = _nucleo_y_esquinas(alto, ancho)
    if esquinas.sum() < 8 or not nucleo.any():
        return otsu  # recorte diminuto: no hay asfalto de referencia

    # Otsu se da por bueno si no invade las esquinas ni deja el centro casi vacío.
    dentro = otsu > 0
    otsu_nucleo, otsu_esquinas = float(dentro[nucleo].mean()), float(dentro[esquinas].mean())
    if (otsu_esquinas <= cfg.huecos_desborde_esquinas
            and otsu_nucleo >= cfg.huecos_nucleo_minimo):
        return otsu

    alternativa = _mascara_rareza(_rareza(gris, color, esquinas), nucleo, limpieza, cfg)
    dentro = alternativa > 0
    alt_nucleo, alt_esquinas = float(dentro[nucleo].mean()), float(dentro[esquinas].mean())
    # Si el hueco llena el recuadro, las esquinas no son asfalto y la rareza no encuentra
    # nada (o se desborda también): entonces se queda Otsu, que lo cubre entero.
    if (alt_nucleo < cfg.huecos_alternativa_nucleo
            or alt_esquinas > cfg.huecos_alternativa_esquinas
            or alt_nucleo - alt_esquinas <= otsu_nucleo - otsu_esquinas):
        return otsu
    return alternativa


# --- Grietas (D00, D10) ---------------------------------------------------------------
# Orientaciones (dx, dy) en las que se mide si un píxel es más oscuro que sus dos lados.
_DIRECCIONES = ((1, 0), (0, 1), (1, 1), (1, -1), (2, 1), (1, 2), (2, -1), (1, -2))


def _percentil_u8(imagen: np.ndarray, q: float) -> float:
    """Percentil de una imagen uint8 por histograma: mucho más rápido que np.percentile."""
    acumulado = np.cumsum(np.bincount(imagen.ravel(), minlength=256))
    return float(np.searchsorted(acumulado, q / 100 * (acumulado[-1] - 1), side="right"))


def _desplazamientos(dist_max: int) -> list[tuple[int, int]]:
    """Vectores en 8 orientaciones con longitudes de 2 a dist_max píxeles, sin repetir."""
    vistos: list[tuple[int, int]] = []
    for dx, dy in _DIRECCIONES:
        norma = float(np.hypot(dx, dy))
        for d in range(2, dist_max + 1):
            k = max(1, round(d / norma))
            if (dx * k, dy * k) not in vistos:
                vistos.append((dx * k, dy * k))
    return vistos


def _valles(suave: np.ndarray, mad: float, cfg: ConfigSegmentacion) -> np.ndarray:
    """Profundidad de valle: cuánto más oscuro es el píxel que AMBOS lados en alguna orientación.

    A diferencia del black-hat no responde al borde de una mancha o de una línea pintada
    (ahí solo un lado es más claro), y no hace falta recortar los brillos, lo que borraba
    las grietas dentro de la pintura. Si los dos lados difieren mucho (borde de sombra, de
    parche o de pintura con un ribete oscuro) la respuesta se penaliza.
    """
    alto, ancho = suave.shape
    dist_max = int(cfg.grieta_valle_dist_max)
    b = 2 * dist_max + 1
    ext = cv2.copyMakeBorder(suave, b, b, b, b, cv2.BORDER_REFLECT)
    salida = np.zeros((alto, ancho), np.uint8)
    alfa = float(cfg.grieta_asimetria)
    tolerancia = float(round(cfg.grieta_asimetria_tolerancia * mad))
    for ox, oy in _desplazamientos(dist_max):
        a = ext[b + oy:b + oy + alto, b + ox:b + ox + ancho]
        c = ext[b - oy:b - oy + alto, b - ox:b - ox + ancho]
        r = cv2.subtract(cv2.min(a, c), suave)  # aritmética saturada: lo negativo queda en 0
        if alfa:
            r = cv2.subtract(r, cv2.multiply(cv2.subtract(cv2.absdiff(a, c), tolerancia), alfa))
        cv2.max(salida, r, dst=salida)
    return salida


def _pintura(recorte: np.ndarray, suave: np.ndarray, mediana: float, mad: float,
             cfg: ConfigSegmentacion) -> np.ndarray:
    """Marcas viales: muy claras (blancas) o amarillas/naranjas bastante saturadas."""
    clara = suave > mediana + max(cfg.grieta_pintura_delta, 4 * mad)
    if recorte.ndim == 3:
        hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
        tono, sat = hsv[..., 0], hsv[..., 1]
        ms = _percentil_u8(sat, 50)
        mads = _percentil_u8(cv2.absdiff(sat, ms), 50) + 1.0
        clara |= (sat > ms + max(20.0, 4 * mads)) & (tono >= 8) & (tono <= 40) & (suave >= mediana)
    # Se descartan los granos claros sueltos del agregado.
    _, etiquetas, est, _ = cv2.connectedComponentsWithStats(clara.astype(np.uint8), connectivity=8)
    grandes = np.flatnonzero(est[:, cv2.CC_STAT_AREA] >= cfg.grieta_pintura_area_min)
    return np.isin(etiquetas, grandes[grandes > 0]).astype(np.uint8)


def _sin_pintura(z: np.ndarray, recorte: np.ndarray, suave: np.ndarray, mediana: float,
                 mad: float, cfg: ConfigSegmentacion) -> None:
    """Anula en z los valles que forman las marcas viales, pero conserva grietas en la pintura.

    - Franja alrededor del borde de la pintura: ribetes oscuros y asfalto entre líneas
      dobles o franjas de paso de peatones (el cierre las une en una sola marca).
    - Dentro de la pintura solo cuenta lo bastante oscuro: una grieta, no una mancha clara.
    """
    pintura = _pintura(recorte, suave, mediana, mad, cfg)
    if not pintura.any():
        return
    nucleo = _elipse(2 * int(cfg.grieta_pintura_radio) + 1)
    unida = cv2.morphologyEx(pintura, cv2.MORPH_CLOSE, nucleo)
    interior = cv2.erode(unida, nucleo) > 0
    cerca = cv2.dilate(unida, nucleo) > 0
    fuera = ~cerca
    nivel = float(np.median(suave[fuera])) if fuera.sum() > 0.1 * suave.size else mediana
    nivel_pintura = float(np.median(suave[pintura > 0]))
    corte = nivel + cfg.grieta_pintura_frac * (nivel_pintura - nivel)
    z[cerca & ~interior] = 0
    z[interior & (suave > corte)] = 0


def _camino(costo: np.ndarray, penal: float) -> np.ndarray:
    """Columna por fila del camino de arriba abajo (saltos de ±1) que maximiza la suma del costo."""
    alto, ancho = costo.shape
    acum = np.empty((alto, ancho + 2), np.float32)
    acum[:, 0] = acum[:, -1] = -1e9
    acum[0, 1:-1] = costo[0]
    for r in range(1, alto):
        previa, fila = acum[r - 1], acum[r, 1:-1]
        np.maximum(previa[:-2], previa[2:], out=fila)
        fila -= penal
        np.maximum(fila, previa[1:-1], out=fila)
        fila += costo[r]
    cols = np.empty(alto, np.int32)
    j = int(acum[-1, 1:-1].argmax()) + 1
    for r in range(alto - 1, 0, -1):
        cols[r] = j - 1
        previa = acum[r - 1]
        mejor = j
        if previa[j - 1] - penal > previa[mejor]:
            mejor = j - 1
        if previa[j + 1] - penal > previa[mejor]:
            mejor = j + 1
        j = mejor
    cols[0] = j - 1
    return cols


def _camino_vertical(z: np.ndarray, tope: float) -> np.ndarray:
    """Camino a lo largo de las filas de z: se calcula a escala reducida y se refina."""
    alto, ancho = z.shape
    f = max(1.0, alto / 120)  # el costo crece con las filas (bucle en Python): máximo 120
    costo = np.minimum(z, tope)
    if f > 1:
        costo = cv2.resize(costo, (max(1, round(ancho / f)), max(1, round(alto / f))),
                           interpolation=cv2.INTER_AREA)
    cols = _camino(costo, 0.05)
    if f > 1:
        centro = (np.arange(len(cols)) + 0.5) * (alto / len(cols)) - 0.5
        cols = np.interp(np.arange(alto), centro, (cols + 0.5) * (ancho / costo.shape[1]) - 0.5)
        # En cada fila se toma el máximo de z cerca del camino escalado.
        radio = int(np.ceil(f)) + 1
        cand = np.round(cols).astype(np.int32)[:, None] + np.arange(-radio, radio + 1)
        cand = np.clip(cand, 0, ancho - 1)
        filas = np.arange(alto)
        cols = cand[filas, np.minimum(z[filas[:, None], cand], tope).argmax(1)]
    return cols.astype(np.int32)


def _trazar(z: np.ndarray, cfg: ConfigSegmentacion) -> tuple[np.ndarray, np.ndarray]:
    """Camino de punta a punta por el eje largo del recuadro: YOLO encuadra la grieta entera.

    En recuadros casi cuadrados la grieta puede ir en cualquier sentido: se prueban los dos
    y gana el camino con más evidencia de grieta (z por encima del nivel de la textura).
    """
    alto, ancho = z.shape
    tope = 4.0  # una mancha muy oscura no debe arrastrar el camino
    cuadrado = max(alto, ancho) / min(alto, ancho) < cfg.grieta_cuadrado_ratio
    candidatos = []
    if alto >= ancho or cuadrado:
        candidatos.append((np.arange(alto), _camino_vertical(z, tope)))
    if ancho > alto or cuadrado:
        candidatos.append((_camino_vertical(np.ascontiguousarray(z.T), tope), np.arange(ancho)))
    evidencia = [float(np.clip(z[ys, xs] - 1, 0, tope - 1).sum()) for ys, xs in candidatos]
    return candidatos[int(np.argmax(evidencia))]


def _semillas_camino(z: np.ndarray, ys: np.ndarray, xs: np.ndarray, umbral: float,
                     largo_min: float, cfg: ConfigSegmentacion) -> np.ndarray:
    """Píxeles del camino que están sobre la grieta: media móvil de z por encima del umbral.

    Los huecos cortos entre dos tramos se rellenan: ahí el camino sigue la grieta aunque
    se vuelva tenue (grietas punteadas o poco contrastadas).
    """
    v = cv2.dilate(z, np.ones((3, 3), np.uint8))[ys, xs]  # tolera 1 px de desvío
    largo = len(v)
    w = max(7, round(largo * cfg.grieta_tramo_ventana)) | 1
    media = np.convolve(np.pad(v, w // 2, mode="edge"), np.ones(w) / w, mode="valid")
    en_grieta = media >= umbral
    sel = en_grieta & (v >= cfg.grieta_semilla_min)
    idx = np.flatnonzero(en_grieta)
    hueco_max = cfg.grieta_hueco_max * largo
    for s in np.flatnonzero(np.diff(idx) > 1):
        if idx[s + 1] - idx[s] - 1 <= hueco_max:
            sel[idx[s] + 1:idx[s + 1]] = True
    if largo_min > 0:
        bordes = np.flatnonzero(np.diff(np.concatenate([[0], sel.astype(np.int8), [0]])))
        for ini, fin in zip(bordes[::2], bordes[1::2], strict=True):
            if fin - ini < largo_min:
                sel[ini:fin] = False
    semillas = np.zeros(z.shape, np.uint8)
    semillas[ys[sel], xs[sel]] = 255
    return semillas


def _lineas(canal: np.ndarray, recorte: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    alto, ancho = canal.shape
    # Sin CLAHE: realza la textura del asfalto, que compite con las grietas finas. El
    # suavizado es mínimo para no borrar grietas de 1 o 2 píxeles.
    suave = cv2.GaussianBlur(canal, (3, 3), 0)
    mediana = _percentil_u8(suave, 50)
    mad = _percentil_u8(cv2.absdiff(suave, mediana), 50) + 1.0
    realce = _valles(suave, mad, cfg)
    # z: respuesta en unidades del nivel de la textura del propio recorte. Así los umbrales
    # valen igual en asfalto liso y rugoso, y no fijan de antemano la fracción marcada.
    escala = max(_percentil_u8(realce, cfg.grieta_escala_percentil),
                 cfg.grieta_escala_minima)
    z = realce.astype(np.float32) / escala
    _sin_pintura(z, recorte, suave, mediana, mad, cfg)

    # Grieta principal: tramos del camino de punta a punta.
    ys, xs = _trazar(z, cfg)
    semillas = _semillas_camino(z, ys, xs, cfg.grieta_tramo_umbral, 0, cfg)
    if semillas.any():
        # Rama o segunda grieta: otro camino lejos del primero, solo con tramos claros y largos.
        radio = max(3, round(min(alto, ancho) * cfg.grieta_rama_exclusion))
        z2 = z.copy()
        z2[cv2.dilate(semillas, _elipse(2 * radio + 1)) > 0] = 0
        # En el borde del recorte suele haber cambios de pavimento cortados, no ramas.
        z2[:3], z2[-3:], z2[:, :3], z2[:, -3:] = 0, 0, 0, 0
        ys2, xs2 = _trazar(z2, cfg)
        largo_rama = cfg.grieta_rama_largo * max(alto, ancho)
        semillas |= _semillas_camino(z2, ys2, xs2, cfg.grieta_rama_umbral, largo_rama, cfg)

    # Ancho de la grieta: crecimiento corto desde el camino por los píxeles de valle,
    # limitado en pasos para no desbordarse por la textura vecina.
    debil = (z >= cfg.grieta_crecer_umbral).astype(np.uint8) * 255
    mascara = semillas
    for _ in range(int(cfg.grieta_crecer_pasos)):
        mascara = cv2.dilate(mascara, np.ones((3, 3), np.uint8)) & debil | semillas
    return cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, _elipse(3))


# --- Piel de cocodrilo (D20) ---------------------------------------------------------------
# La malla se reconoce por la DENSIDAD de grietas, no por cada grieta. Todo se calcula a una
# escala de trabajo fija (área normalizada), así los tamaños no dependen del recorte. Lo que es
# de gran escala (iluminación, densidad, sombras, vegetación) va a media resolución.


def _a_mitad(img: np.ndarray) -> np.ndarray:
    alto, ancho = img.shape[:2]
    return cv2.resize(img, (max(1, ancho // 2), max(1, alto // 2)), interpolation=cv2.INTER_AREA)


def _mediana(img: np.ndarray, tamano: int) -> np.ndarray:
    """Mediana con la ventana recortada al tamaño de la imagen."""
    tope = max(3, min(img.shape[:2]) // 2 * 2 - 1)
    return cv2.medianBlur(img, _impar(min(tamano, tope)))


def _sombra(color: np.ndarray, gris: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    """Sombra que cubre una parte minoritaria del recuadro: región ancha, más oscura que la zona
    iluminada y más azul (a la sombra la ilumina el cielo). Un parche de asfalto oscuro con malla
    no es más azul que el resto y se conserva.
    """
    nada = np.zeros(gris.shape, bool)
    # El nivel iluminado es un percentil alto: si la sombra cubre casi todo el recuadro, sale
    # oscura entera y la regla de mayoría (al final) la conserva, porque la malla está en ella.
    nivel = float(np.percentile(gris, 75))
    oscuro = gris < nivel * cfg.malla_sombra_rel
    if not oscuro.any() or oscuro.all():
        return nada
    b, g, r = (cv2.blur(color[..., k], (3, 3)).astype(np.float32) for k in range(3))
    azul = 3 * (b - r) / (b + g + r + 1)
    sombra = oscuro & (azul > float(np.median(azul[~oscuro])) + cfg.malla_sombra_azul)
    # Una sombra es ancha: la apertura borra las grietas oscuras y las motas.
    sombra = cv2.morphologyEx(sombra.astype(np.uint8), cv2.MORPH_OPEN, _elipse(5))
    sombra = cv2.morphologyEx(sombra, cv2.MORPH_CLOSE, _elipse(5))
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(sombra)
    grandes = stats[:, cv2.CC_STAT_AREA] >= 0.03 * sombra.size
    grandes[0] = False
    sombra = grandes[etiquetas]
    return nada if sombra.mean() > 0.5 else sombra


def _vegetacion(color: np.ndarray, cfg: ConfigSegmentacion) -> np.ndarray:
    """Verde claramente por encima del rojo y del azul (el asfalto puede tener un tinte verdoso;
    la pintura amarilla tiene el verde alto, pero no por encima del rojo).
    """
    b, g, r = (color[..., k].astype(np.int16) for k in range(3))
    verde = (((2 * g - r - b) > cfg.malla_vegetacion_verde) & (g > r + 8)).astype(np.uint8)
    return cv2.dilate(cv2.morphologyEx(verde, cv2.MORPH_OPEN, _elipse(3)), _elipse(3)) > 0


def _rellenar_huecos(region: np.ndarray, fraccion_max: float) -> np.ndarray:
    """Rellena los huecos interiores pequeños: dentro de la malla, una celda sin grietas es malla."""
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats((~region).astype(np.uint8), connectivity=4)
    pequenos = stats[:, cv2.CC_STAT_AREA] < fraccion_max * region.size
    tocan_borde = np.concatenate([etiquetas[0], etiquetas[-1], etiquetas[:, 0], etiquetas[:, -1]])
    pequenos[np.unique(tocan_borde)] = False
    pequenos[0] = False
    return region | pequenos[etiquetas]


def _etapas_malla(gris: np.ndarray, cfg: ConfigSegmentacion, color: np.ndarray | None = None,
                  depurar: bool = False) -> dict[str, np.ndarray]:
    """Región de malla a media resolución de trabajo ("region"); con depurar, también las etapas."""
    alto, ancho = gris.shape[:2]
    escala = min(cfg.malla_lado_px / np.sqrt(alto * ancho), 3.0)
    tam = (max(8, round(ancho * escala)), max(8, round(alto * escala)))
    interp = cv2.INTER_AREA if escala < 1 else cv2.INTER_LINEAR
    trabajo = cv2.resize(gris, tam, interpolation=interp)
    g = cv2.GaussianBlur(trabajo, (3, 3), 0).astype(np.float32)

    # 1. Iluminación local: mediana ancha (a media resolución). Sigue el borde de una sombra
    #    sin difuminarlo y no la arrastran las grietas, que ocupan menos de media ventana.
    mitad = _a_mitad(trabajo)
    ilum_mitad = _mediana(mitad, cfg.malla_iluminacion_px // 2).astype(np.float32)
    ilum = cv2.resize(ilum_mitad, tam, interpolation=cv2.INTER_LINEAR)

    # 2. Grietas: black-hat pequeño sobre la imagen con los brillos recortados al nivel local
    #    (una marca vial no levanta el fondo ni crea un valle en el asfalto vecino). Dentro de
    #    la pintura no se recorta, para ver la pintura agrietada.
    k_bh = _elipse(cfg.malla_kernel_px)
    realce = cv2.morphologyEx(np.minimum(g, ilum), cv2.MORPH_BLACKHAT, k_bh)
    pintura = (g > ilum * 1.3) & (g > ilum + cfg.malla_pintura_min)
    pintura = cv2.morphologyEx(pintura.astype(np.uint8), cv2.MORPH_CLOSE, _elipse(5))
    pintura = cv2.erode(pintura, _elipse(3))
    realce = np.where(pintura > 0, cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k_bh), realce)
    # Contraste en unidades de ruido (el ruido de cámara crece como la raíz del brillo): las
    # grietas en sombra cuentan, pero el grano amplificado de una sombra oscura no domina.
    realce /= np.sqrt(ilum + 10)
    # Saltos fuertes de iluminación (borde de sombra, bordillo): su lado oscuro no es grieta.
    salto = cv2.morphologyEx(np.log(ilum_mitad + 10), cv2.MORPH_GRADIENT, _elipse(5))
    borde = cv2.dilate((salto > 0.35).astype(np.uint8), _elipse(3))
    realce[cv2.resize(borde, tam, interpolation=cv2.INTER_NEAREST) > 0] = 0
    # La fracción más fuerte del realce: en un recuadro todo malla queda repartida; si la malla
    # cubre una parte, se concentra en ella.
    q = cfg.malla_fraccion_grietas
    grietas = (realce > max(float(np.percentile(realce, 100 * (1 - q))), 1e-6)).astype(np.float32)

    # 3. Densidad de grietas (media resolución), umbral relativo a la densidad media.
    grietas_mitad = _a_mitad(grietas)
    densidad = cv2.GaussianBlur(grietas_mitad, (0, 0), cfg.malla_sigma_px / 2)
    region = densidad > cfg.malla_densidad_rel * float(grietas.mean())
    region = _rellenar_huecos(region, 0.08)

    # 4. Exclusiones: pintura sin grietas, sombras minoritarias y vegetación.
    #    La pintura agrietada es malla; la limpia (sin grietas cerca) no. Las grietas anchas
    #    quedan fuera de la máscara de pintura, por eso se mira la densidad local alrededor.
    cerca = cv2.GaussianBlur(grietas_mitad, (0, 0), 3)
    limpia = (_a_mitad(pintura) > 0) & (cerca < 0.4 * q)
    excluir = cv2.dilate(limpia.astype(np.uint8), _elipse(3)) > 0
    if color is not None:
        color_mitad = cv2.resize(color, (mitad.shape[1], mitad.shape[0]), interpolation=cv2.INTER_AREA)
        excluir |= _sombra(color_mitad, _mediana(mitad, 7), cfg) | _vegetacion(color_mitad, cfg)
    region = (region & ~excluir).astype(np.uint8) * 255
    region = cv2.morphologyEx(region, cv2.MORPH_OPEN, _elipse(3))

    if not depurar:
        return {"region": region}

    def a_u8(m):
        return cv2.normalize(m.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    return {"pintura": pintura * 255, "realce": a_u8(realce), "grietas": a_u8(grietas),
            "densidad": a_u8(densidad), "excluir": a_u8(excluir), "region": region}


def _malla(gris: np.ndarray, cfg: ConfigSegmentacion, color: np.ndarray | None = None) -> np.ndarray:
    region = _etapas_malla(gris, cfg, color)["region"]
    region = cv2.resize(region, (gris.shape[1], gris.shape[0]), interpolation=cv2.INTER_LINEAR)
    return np.where(region > 127, 255, 0).astype(np.uint8)


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
        binaria = _region(gris, cfg, recorte if recorte.ndim == 3 else None)
    elif modo == "linea":
        # Canal máximo (V) en vez de gris: la pintura amarilla queda tan clara como la blanca.
        canal = recorte.max(axis=2) if recorte.ndim == 3 else gris
        binaria = _lineas(canal, recorte, cfg)
    else:
        binaria = _malla(gris, cfg, recorte if recorte.ndim == 3 else None)

    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # En grietas cada tramo sale de un camino validado: un área mínima borraría las finas.
    if modo != "linea":
        contornos = [c for c in contornos if cv2.contourArea(c) >= cfg.area_minima_px]
    mascara = vacia
    if contornos:
        cv2.drawContours(mascara, contornos, -1, 255, cv2.FILLED)
    return Segmentacion(mascara, contornos)
