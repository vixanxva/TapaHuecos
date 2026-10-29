"""Reporta las métricas del proyecto.

Métricas del modelo, sobre el conjunto de prueba (precisión, exhaustividad, F1,
mAP@0.5 y mAP@0.5:0.95 por clase):
    python scripts/evaluar.py modelo --pesos modelos/best.pt --datos datos/combinado/data.yaml

Métricas de campo, sobre los recorridos de Montería (precisión con los daños
revisados por `tapahuecos revisar`; exhaustividad si se entrega la verdad de campo):
    python scripts/evaluar.py campo --db salidas/danos.db --verdad datos/verdad_campo.csv

El CSV de verdad de campo tiene columnas: latitud,longitud[,clase]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tapahuecos.evaluacion import evaluar_campo  # noqa: E402
from tapahuecos.registro import BaseDatos  # noqa: E402


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def _fmt(valor) -> str:
    return "—" if valor is None else f"{valor:.3f}"


def evaluar_modelo(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    metricas = YOLO(args.pesos).val(
        data=args.datos, split=args.split, imgsz=args.imgsz, plots=True, verbose=False
    )
    caja = metricas.box
    filas = []
    for i, indice in enumerate(caja.ap_class_index):
        p, r, ap50, ap = caja.class_result(i)
        filas.append({"clase": metricas.names[int(indice)], "precision": p, "exhaustividad": r,
                      "f1": _f1(p, r), "mAP50": ap50, "mAP50_95": ap})
    filas.append({"clase": "todas", "precision": caja.mp, "exhaustividad": caja.mr,
                  "f1": _f1(caja.mp, caja.mr), "mAP50": caja.map50, "mAP50_95": caja.map})
    velocidad = metricas.speed  # ms por imagen: preprocess, inference, postprocess

    lineas = [
        f"# Métricas del modelo ({args.split})", "",
        f"Modelo: `{args.pesos}` · Datos: `{args.datos}`", "",
        "| Clase | Precisión | Exhaustividad | F1 | mAP@0.5 | mAP@0.5:0.95 |",
        "|---|---|---|---|---|---|",
        *(f"| {f['clase']} | {f['precision']:.3f} | {f['exhaustividad']:.3f} | {f['f1']:.3f} "
          f"| {f['mAP50']:.3f} | {f['mAP50_95']:.3f} |" for f in filas),
        "", f"Inferencia: {velocidad.get('inference', 0):.1f} ms/imagen "
            f"(en el hardware donde se ejecutó esta evaluación).",
    ]
    _guardar(args.salida, f"modelo_{args.split}", lineas,
             {"filas": [{k: float(v) if k != "clase" else v for k, v in f.items()} for f in filas],
              "velocidad_ms": velocidad})


def evaluar_en_campo(args: argparse.Namespace) -> None:
    with BaseDatos(args.db) as bd:
        filas = bd.danos()
    verdad = None
    if args.verdad:
        import pandas as pd

        verdad = pd.read_csv(args.verdad).to_dict("records")
    m = evaluar_campo(filas, verdad, args.radio, args.misma_clase)
    lineas = [
        "# Métricas de campo", "",
        f"Daños registrados: {len(filas)} · revisados: {m.revisados} · reales: {m.reales}", "",
        "| Métrica | Valor |", "|---|---|",
        f"| Precisión | {_fmt(m.precision)} |",
        f"| Exhaustividad (radio {args.radio:g} m) | {_fmt(m.exhaustividad)} |",
        f"| F1 | {_fmt(m.f1)} |",
    ]
    if m.verdad_total is not None:
        lineas.append(f"\nDaños de la verdad de campo encontrados: {m.encontrados}/{m.verdad_total}")
    _guardar(args.salida, "campo", lineas, {**m.__dict__, "f1": m.f1, "radio_m": args.radio})


def _guardar(carpeta: Path, nombre: str, lineas: list[str], datos: dict) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(lineas) + "\n"
    (carpeta / f"{nombre}.md").write_text(texto, encoding="utf-8")
    (carpeta / f"{nombre}.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), "utf-8")
    print(texto)
    print(f"Guardado en {carpeta / nombre}.md y .json")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--salida", type=Path, default=Path("reportes"))
    sub = p.add_subparsers(dest="modo", required=True)

    m = sub.add_parser("modelo", help="métricas sobre el conjunto de prueba")
    m.add_argument("--pesos", default="modelos/best.pt")
    m.add_argument("--datos", required=True)
    m.add_argument("--split", default="test", choices=["val", "test"])
    m.add_argument("--imgsz", type=int, default=640)
    m.set_defaults(funcion=evaluar_modelo)

    c = sub.add_parser("campo", help="métricas sobre los recorridos reales")
    c.add_argument("--db", type=Path, default=Path("salidas/danos.db"))
    c.add_argument("--verdad", type=Path, help="CSV con latitud,longitud[,clase]")
    c.add_argument("--radio", type=float, default=10.0, help="metros para considerar coincidencia")
    c.add_argument("--misma-clase", action="store_true", help="exigir que coincida la clase")
    c.set_defaults(funcion=evaluar_en_campo)

    args = p.parse_args()
    args.funcion(args)


if __name__ == "__main__":
    main()
