"""Métricas de campo: qué tan bien funciona el sistema en las calles de Montería.

Complementan las métricas del modelo (mAP, precisión, exhaustividad sobre el
conjunto de prueba) que calcula Ultralytics en scripts/evaluar.py.
"""

from __future__ import annotations

from dataclasses import dataclass

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
