"""Métricas de campo: qué tan bien funciona el sistema en las calles de Montería.

Complementan las métricas del modelo (mAP, precisión, exhaustividad sobre el
conjunto de prueba) que calcula Ultralytics en scripts/evaluar.py.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from tapahuecos.gps import distancia_m


@dataclass
class MetricasCampo:
    revisados: int
    reales: int
    precision: float | None  # reales / revisados
    verdad_total: int | None = None
    encontrados: int | None = None
    exhaustividad: float | None = None  # encontrados / verdad_total

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.exhaustividad
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)


def evaluar_campo(
    filas: list[dict],
    verdad: list[dict] | None = None,
    radio_m: float = 10.0,
    misma_clase: bool = False,
) -> MetricasCampo:
    """Calcula precisión con los registros revisados a mano (`tapahuecos revisar`).

    Si se entrega `verdad` (filas con latitud, longitud y opcionalmente clase,
    levantadas recorriendo la vía), calcula también la exhaustividad: fracción de
    daños reales que tienen una detección a menos de `radio_m` metros.
    """
    revisadas = [f for f in filas if f.get("verificado") is not None]
    reales = sum(1 for f in revisadas if f["verificado"] == 1)
    metricas = MetricasCampo(
        revisados=len(revisadas),
        reales=reales,
        precision=reales / len(revisadas) if revisadas else None,
    )
    if verdad is None:
        return metricas

    candidatas = [
        f for f in filas
        if f.get("latitud") is not None and f.get("verificado") != 0  # descarta falsos marcados
    ]
    encontrados = 0
    for punto in verdad:
        for f in candidatas:
            if misma_clase and punto.get("clase") and punto["clase"] != f["clase"]:
                continue
            d = distancia_m(punto["latitud"], punto["longitud"], f["latitud"], f["longitud"])
            if d <= radio_m:
                encontrados += 1
                break
    metricas.verdad_total = len(verdad)
    metricas.encontrados = encontrados
    metricas.exhaustividad = encontrados / len(verdad) if verdad else None
    return metricas


@dataclass
class ParHueco:
    """Un hueco medido con cinta y el D40 registrado que le corresponde."""

    medido: int  # posición en la lista de huecos medidos
    registro_id: int
    distancia_m: float
    area_real_m2: float | None
    area_estimada_m2: float | None

    @property
    def error_area(self) -> float | None:
        """|estimada − real| / real, o None si falta alguna de las dos áreas."""
        real, estimada = self.area_real_m2, self.area_estimada_m2
        if real is None or estimada is None or real <= 0:
            return None
        return abs(estimada - real) / real


@dataclass
class ErrorArea:
    n_medidos: int
    n_emparejados: int
    area_media: float | None = None  # error porcentual, como fracción (0.25 = 25 %)
    area_mediana: float | None = None
    area_maximo: float | None = None
    posicion_media_m: float | None = None
    posicion_mediana_m: float | None = None
    posicion_maximo_m: float | None = None
    pares: list[ParHueco] = field(default_factory=list)


def emparejar_huecos(
    filas: list[dict],
    medidos: list[dict],
    radio_m: float = 10.0,
    clase: str = "D40",
) -> list[ParHueco]:
    """Empareja uno a uno cada hueco medido con el registro de `clase` más cercano.

    Descarta los registros marcados como falsos (verificado = 0) y los que no tienen
    coordenada. El emparejamiento es voraz: se recorren los pares a menos de `radio_m`
    de menor a mayor distancia y cada hueco y cada registro se usan una sola vez.
    """
    candidatas = [
        f for f in filas
        if f.get("clase") == clase and f.get("latitud") is not None and f.get("verificado") != 0
    ]
    posibles = []
    for i, hueco in enumerate(medidos):
        for f in candidatas:
            d = distancia_m(hueco["latitud"], hueco["longitud"], f["latitud"], f["longitud"])
            if d <= radio_m:
                posibles.append((d, i, f))
    posibles.sort(key=lambda p: (p[0], p[1], p[2]["id"]))

    pares: list[ParHueco] = []
    usados_medidos: set[int] = set()
    usados_registros: set[int] = set()
    for d, i, f in posibles:
        if i in usados_medidos or f["id"] in usados_registros:
            continue
        usados_medidos.add(i)
        usados_registros.add(f["id"])
        pares.append(ParHueco(i, f["id"], d, medidos[i].get("area_m2"), f.get("area_m2")))
    return sorted(pares, key=lambda p: p.medido)


def evaluar_area(
    filas: list[dict],
    medidos: list[dict],
    radio_m: float = 10.0,
    clase: str = "D40",
) -> ErrorArea:
    """Error de área y de posición de los huecos medidos con cinta en campo."""
    pares = emparejar_huecos(filas, medidos, radio_m, clase)
    resultado = ErrorArea(n_medidos=len(medidos), n_emparejados=len(pares), pares=pares)
    errores = [p.error_area for p in pares if p.error_area is not None]
    if errores:
        resultado.area_media = statistics.mean(errores)
        resultado.area_mediana = statistics.median(errores)
        resultado.area_maximo = max(errores)
    if pares:
        distancias = [p.distancia_m for p in pares]
        resultado.posicion_media_m = statistics.mean(distancias)
        resultado.posicion_mediana_m = statistics.median(distancias)
        resultado.posicion_maximo_m = max(distancias)
    return resultado
