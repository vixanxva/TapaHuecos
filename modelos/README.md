# Modelos (no versionados)

Los pesos `.pt` no se suben a Git. Después de entrenar, súbalos a Google Drive y
anótelos aquí. La carpeta del equipo es
[Drive/TapaHuecos](https://drive.google.com/drive/folders/1Brwtdk58xGeuQZ6DTQ9rDuyQA4E9Vcl7?usp=sharing)
(ver también [datos/README.md](../datos/README.md)).

| Archivo | Datos | Base | mAP@0.5 (validación) | mAP@0.5 (test) | mAP@0.5:0.95 (test) | Enlace |
|---|---|---|---|---|---|---|
| `best_rdd.pt` | RDD2022 | yolov8s.pt | 0.643 | 0.633 | 0.329 | Drive del equipo (fase 1) |
| `best.pt` | RDD2022 + Montería | `best_rdd.pt` | — | — | — | **Falta** |

## `best_rdd.pt` (fase 1)

- Entrenado con RDD2022 durante 85 épocas (~6 h 35 min en una GPU T4).
- Tamaño local: 22,530,474 bytes.
- Métricas de test por clase en `reportes/modelo_test.md` (no versionado).
- Punto débil conocido: **D40 (huecos)**, recall 0.445 y mAP@0.5 0.505. Ver issue #47.
- `runs/rdd_completo/weights/last.pt` es el último checkpoint del mismo
  entrenamiento; para procesar se usa `best_rdd.pt`.

## `best.pt` (fase 2)

Todavía no existe en esta copia local. Se obtiene al ajustar `best_rdd.pt` con el
dataset combinado de RDD2022 y las fotos etiquetadas de Montería. Sin la exportación
de Roboflow (`datos/monteria/`) no se puede reproducir; ver issue #10.
