"""Etapa 4: ubicar cada fotograma en el recorrido GPX grabado con el celular."""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import gpxpy

RADIO_TIERRA_M = 6_371_000.0


@dataclass(frozen=True)
class PuntoGPS:
    instante: datetime
    latitud: float
    longitud: float


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la superficie terrestre (fórmula del haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


class Recorrido:
    def __init__(self, puntos: list[PuntoGPS], max_hueco_s: float = 30.0):
        if not puntos:
            raise ValueError("El recorrido no tiene puntos con hora.")
        self.puntos = sorted(puntos, key=lambda p: p.instante)
        self._t = [p.instante.timestamp() for p in self.puntos]
        self.max_hueco_s = max_hueco_s

    @classmethod
    def desde_gpx(cls, ruta: str | Path) -> Recorrido:
        with open(ruta, encoding="utf-8") as archivo:
            gpx = gpxpy.parse(archivo)
        puntos = [
            PuntoGPS(
                p.time if p.time.tzinfo else p.time.replace(tzinfo=timezone.utc),
                p.latitude,
                p.longitude,
            )
            for pista in gpx.tracks
            for segmento in pista.segments
            for p in segmento.points
            if p.time is not None
        ]
        if not puntos:
            raise ValueError(f"{ruta} no contiene puntos de recorrido con hora (trkpt con <time>).")
        return cls(puntos)

    @property
    def inicio(self) -> datetime:
        return self.puntos[0].instante

    @property
    def fin(self) -> datetime:
        return self.puntos[-1].instante

    def posicion(self, instante: datetime, tolerancia_s: float = 5.0) -> tuple[float, float] | None:
        """Latitud y longitud en ese instante, interpolando entre los dos puntos vecinos.

        Devuelve None si el instante cae fuera del recorrido (más allá de la tolerancia)
        o en un tramo donde el GPS dejó de registrar.
        """
        t = instante.timestamp()
        if t < self._t[0] - tolerancia_s or t > self._t[-1] + tolerancia_s:
            return None
        i = bisect_left(self._t, t)
        if i == 0:
            return self.puntos[0].latitud, self.puntos[0].longitud
        if i == len(self._t):
            return self.puntos[-1].latitud, self.puntos[-1].longitud

        a, b = self.puntos[i - 1], self.puntos[i]
        ta, tb = self._t[i - 1], self._t[i]
        if tb - ta > self.max_hueco_s:
            cercano, dt = (a, t - ta) if t - ta <= tb - t else (b, tb - t)
            return (cercano.latitud, cercano.longitud) if dt <= tolerancia_s else None
        fraccion = (t - ta) / (tb - ta) if tb > ta else 0.0
        return (
            a.latitud + fraccion * (b.latitud - a.latitud),
            a.longitud + fraccion * (b.longitud - a.longitud),
        )
