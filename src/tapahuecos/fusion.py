"""Fusión de daños repetidos entre recorridos.

Si la misma calle se recorre varias veces, el mismo hueco queda registrado una vez
por recorrido. Aquí se agrupan los registros de la misma clase que están a menos de
`radio_m` metros, para que el mapa y el resumen muestren daños únicos.

Se agrupa alrededor de semillas, sin encadenar: si A está cerca de B y B cerca de C,
C no entra al grupo de A salvo que también esté cerca de A. Así una grieta larga,
registrada en tramos consecutivos, no termina convertida en un único daño.
Un grupo admite como máximo un registro por recorrido, porque dentro de un mismo
recorrido el seguidor ya distingue los daños.
"""

from __future__ import annotations

from tapahuecos.gps import distancia_m
from tapahuecos.registro import BaseDatos


def _prioridad(fila: dict) -> tuple:
    # Confirmados como reales primero, falsos positivos al final, luego la confianza.
    return (fila.get("verificado") == 1, fila.get("verificado") != 0, fila["confianza"])


def agrupar(filas: list[dict], radio_m: float = 8.0, misma_clase: bool = True) -> dict[int, int]:
    """Devuelve {id del daño: id del grupo}. El id del grupo es el id de su semilla."""
    candidatas = sorted(
        (f for f in filas if f["latitud"] is not None and f["longitud"] is not None),
        key=_prioridad,
        reverse=True,
    )
    grupos: dict[int, int] = {}
    for semilla in candidatas:
        if semilla["id"] in grupos:
            continue
        grupos[semilla["id"]] = semilla["id"]
        recorridos = {semilla["recorrido_id"]}
        cercanas = sorted(
            (
                (distancia_m(semilla["latitud"], semilla["longitud"], f["latitud"], f["longitud"]), f)
                for f in candidatas
                if f["id"] not in grupos and (not misma_clase or f["clase"] == semilla["clase"])
            ),
            key=lambda par: par[0],
        )
        for distancia, fila in cercanas:
            if distancia > radio_m:
                break
            if fila["recorrido_id"] in recorridos:
                continue
            grupos[fila["id"]] = semilla["id"]
            recorridos.add(fila["recorrido_id"])

    for fila in filas:  # sin coordenada: cada uno es su propio grupo
        grupos.setdefault(fila["id"], fila["id"])
    return grupos


def clave_grupo(fila: dict) -> int:
    return fila["grupo"] if fila.get("grupo") is not None else fila["id"]


def unicos(filas: list[dict]) -> list[dict]:
    """Un registro por grupo (el de mayor prioridad), con `registros` = veces que se registró."""
    por_grupo: dict[int, list[dict]] = {}
    for fila in filas:
        por_grupo.setdefault(clave_grupo(fila), []).append(fila)
    resultado = []
    for miembros in por_grupo.values():
        mejor = dict(max(miembros, key=_prioridad))
        mejor["registros"] = len(miembros)
        resultado.append(mejor)
    return sorted(resultado, key=lambda f: f["id"])


def fusionar_bd(bd: BaseDatos, radio_m: float = 8.0, misma_clase: bool = True) -> tuple[int, int]:
    """Recalcula los grupos de toda la base de datos. Devuelve (registros, daños únicos)."""
    filas = bd.danos()
    grupos = agrupar(filas, radio_m, misma_clase)
    bd.asignar_grupos(grupos)
    return len(filas), len(set(grupos.values()))
