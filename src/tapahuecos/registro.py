"""Etapa 5: base de datos SQLite y registro de cada daño una sola vez."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from tapahuecos.clases import ClaseDano

ESQUEMA = """
CREATE TABLE IF NOT EXISTS recorridos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    video         TEXT NOT NULL,
    gpx           TEXT,
    modelo        TEXT NOT NULL,
    procesado_en  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS danos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorrido_id    INTEGER NOT NULL REFERENCES recorridos(id),
    track_id        INTEGER NOT NULL,
    clase           TEXT NOT NULL,
    nombre_clase    TEXT NOT NULL,
    confianza       REAL NOT NULL,
    veces_visto     INTEGER NOT NULL,
    fotograma       INTEGER NOT NULL,
    tiempo_video_s  REAL NOT NULL,
    instante_utc    TEXT,
    latitud         REAL,
    longitud        REAL,
    area_px         INTEGER NOT NULL,
    area_m2         REAL,
    x1 INTEGER NOT NULL, y1 INTEGER NOT NULL, x2 INTEGER NOT NULL, y2 INTEGER NOT NULL,
    recorte         TEXT NOT NULL,             -- ruta relativa a la carpeta de la base de datos
    verificado      INTEGER CHECK (verificado IN (0, 1)),  -- NULL sin revisar, 1 real, 0 falso
    grupo           INTEGER,                   -- el mismo daño visto en varios recorridos
    UNIQUE (recorrido_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_danos_clase ON danos (clase);
"""


@dataclass
class Observacion:
    """Un daño visto en un fotograma concreto."""

    track_id: int
    clase: ClaseDano
    confianza: float
    fotograma: int
    tiempo_video_s: float
    instante_utc: datetime | None
    latitud: float | None
    longitud: float | None
    area_px: int
    area_m2: float | None
    caja: tuple[int, int, int, int]
    recorte: np.ndarray


class BaseDatos:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.ruta)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Agrega a bases de datos creadas con versiones anteriores las columnas nuevas."""
        columnas = {fila["name"] for fila in self.con.execute("PRAGMA table_info(danos)")}
        if "grupo" not in columnas:
            self.con.execute("ALTER TABLE danos ADD COLUMN grupo INTEGER")
            self.con.commit()

    def nuevo_recorrido(self, video: str, gpx: str | None, modelo: str) -> int:
        cursor = self.con.execute(
            "INSERT INTO recorridos (video, gpx, modelo, procesado_en) VALUES (?, ?, ?, ?)",
            (video, gpx, modelo, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def insertar_dano(
        self, recorrido_id: int, obs: Observacion, veces_visto: int, recorte: str
    ) -> int:
        x1, y1, x2, y2 = obs.caja
        cursor = self.con.execute(
            """
            INSERT INTO danos (
                recorrido_id, track_id, clase, nombre_clase, confianza, veces_visto,
                fotograma, tiempo_video_s, instante_utc, latitud, longitud,
                area_px, area_m2, x1, y1, x2, y2, recorte
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recorrido_id, obs.track_id, obs.clase.codigo, obs.clase.nombre,
                round(obs.confianza, 4), veces_visto, obs.fotograma,
                round(obs.tiempo_video_s, 3),
                obs.instante_utc.astimezone(timezone.utc).isoformat(timespec="milliseconds")
                if obs.instante_utc else None,
                obs.latitud, obs.longitud, obs.area_px,
                round(obs.area_m2, 5) if obs.area_m2 is not None else None,
                x1, y1, x2, y2, recorte,
            ),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def danos(self, recorrido_id: int | None = None) -> list[dict]:
        consulta = (
            "SELECT d.*, r.video FROM danos d JOIN recorridos r ON r.id = d.recorrido_id"
        )
        parametros: tuple = ()
        if recorrido_id is not None:
            consulta += " WHERE d.recorrido_id = ?"
            parametros = (recorrido_id,)
        return [dict(fila) for fila in self.con.execute(consulta + " ORDER BY d.id", parametros)]

    def marcar(self, dano_id: int, real: bool) -> None:
        self.con.execute("UPDATE danos SET verificado = ? WHERE id = ?", (int(real), dano_id))
        self.con.commit()

    def asignar_grupos(self, grupos: dict[int, int]) -> None:
        self.con.executemany(
            "UPDATE danos SET grupo = ? WHERE id = ?", [(g, i) for i, g in grupos.items()]
        )
        self.con.commit()

    def cerrar(self) -> None:
        self.con.close()

    def __enter__(self) -> BaseDatos:
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


@dataclass
class _Pista:
    mejor: Observacion
    veces: int
    ultimo_fotograma: int


class GestorDanos:
    """Agrupa las observaciones por ID de seguimiento y guarda cada daño una sola vez.

    Un daño se registra cuando deja de verse (o al terminar el video) y solo si
    apareció en al menos `min_fotogramas` fotogramas, lo que filtra detecciones
    espurias de un único cuadro. Se conserva la observación de mayor confianza.
    """

    def __init__(
        self,
        bd: BaseDatos,
        recorrido_id: int,
        carpeta_recortes: Path,
        min_fotogramas: int = 3,
        max_ausencia: int = 30,
    ):
        self.bd = bd
        self.recorrido_id = recorrido_id
        self.carpeta_recortes = Path(carpeta_recortes)
        self.carpeta_recortes.mkdir(parents=True, exist_ok=True)
        self.min_fotogramas = min_fotogramas
        self.max_ausencia = max_ausencia
        self._pistas: dict[int, _Pista] = {}
        self._cerrados: set[int] = set()
        self.registrados = 0

    def observar(self, obs: Observacion) -> None:
        if obs.track_id in self._cerrados:
            return
        pista = self._pistas.get(obs.track_id)
        if pista is None:
            self._pistas[obs.track_id] = _Pista(obs, 1, obs.fotograma)
            return
        pista.veces += 1
        pista.ultimo_fotograma = obs.fotograma
        if obs.confianza > pista.mejor.confianza:
            pista.mejor = obs

    def cerrar_ausentes(self, fotograma_actual: int) -> None:
        for track_id, pista in list(self._pistas.items()):
            if fotograma_actual - pista.ultimo_fotograma > self.max_ausencia:
                self._cerrar(track_id)

    def finalizar(self) -> int:
        for track_id in list(self._pistas):
            self._cerrar(track_id)
        return self.registrados

    def _cerrar(self, track_id: int) -> None:
        pista = self._pistas.pop(track_id)
        self._cerrados.add(track_id)
        if pista.veces < self.min_fotogramas:
            return
        obs = pista.mejor
        ruta = self.carpeta_recortes / f"{self.recorrido_id:03d}_{track_id:05d}_{obs.clase.codigo}.jpg"
        cv2.imwrite(str(ruta), obs.recorte)
        relativa = Path(os.path.relpath(ruta.resolve(), self.bd.ruta.resolve().parent)).as_posix()
        self.bd.insertar_dano(self.recorrido_id, obs, pista.veces, relativa)
        self.registrados += 1
