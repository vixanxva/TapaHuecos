# Estado actual del proyecto

Fecha de corte: **2026-11-11**. Rama local `avance-local`, creada desde `develop`
(`29148c0`) y **sin rama remota configurada**.

Este documento resume qué está disponible en esta copia local, qué falta para cada
hito del [backlog](backlog.md) y cuál es el siguiente paso verificable. No reemplaza
las issues de GitHub: cuando una tarea ya existe allí, se indica su número.

## Resumen

- El código del pipeline está completo y la suite pasa: **115 pruebas**.
- La fase 1 del modelo está disponible (`modelos/best_rdd.pt`, 22.5 MB) con métricas
  de prueba conocidas. Se instaló Ultralytics en el entorno temporal y se hizo una
  corrida real corta en CPU (ver más abajo).
- El ZIP traído desde Drive es un **snapshot parcial**: contiene 2 de los 6 videos,
  2 GPX que no coinciden con esos videos, solo `RDD2022/Japan.zip`, los pesos de la
  fase 1 y salidas antiguas. No contiene el dataset etiquetado, `best.pt`, la
  calibración ni los CSV de campo.
- Los bloqueos principales son: **no hay un par video+GPX sincronizado**, **no hay
  etiquetas propias para entrenar `best.pt`**, **no hay homografía ni mediciones con
  cinta** y **no está la base de datos revisada en campo**.

## Inventario local

| Insumo | Estado | Detalle |
|---|---|---|
| Videos | Parcial | `datos/videos/VID_20261108_110401.mp4` (1080x1920, 32.4 s) y `VID_20261108_111532.mp4` (1080x1920, 36.2 s). El CSV de `Prueba_region` usa 5 recorridos: faltan los videos `110956`, `111300` y `111705` |
| GPX | Parcial, sin solape | `20261108-111252.gpx` (16:12:52–16:13:42 UTC) y `20261108-111702.gpx` (16:17:02–16:17:49 UTC) |
| RDD2022 | Parcial | Solo `datos/RDD2022/Japan.zip` (1.07 GB); falta convertirlo a `datos/rdd_yolo/` |
| Dataset propio | Falta | No hay `datos/monteria/` (exportación de Roboflow) ni `datos/combinado/` |
| Pesos fase 1 | Disponible | `modelos/best_rdd.pt`, 22,530,474 bytes; también `runs/rdd_completo/weights/last.pt` |
| Pesos fase 2 | Falta | No hay `modelos/best.pt` |
| Calibración | Falta | `calibracion/` solo tiene `.gitkeep`; no hay video de calibración ni `homografia.npy` |
| Verdad de campo | Falta | No hay `datos/verdad_campo.csv` ni `datos/huecos_medidos.csv` |
| Salidas | Parciales y sin revisar | `salidas/danos.db` (15 daños), `salidas/fps_prueba/danos.db` (6) y `salidas/Prueba_region/danos.csv` (48 filas de 5 recorridos); **0 verificados** |
| Reporte de modelo | Disponible, no versionado | `reportes/modelo_test.md`; `runs/rdd_completo/` tiene curvas y matriz de confusión |
| ZIP de Drive | Conservado | `drive-download-20261111T203820Z-1-001.zip` (2.08 GB, 62 entradas); no se modificó ni se borró |

### Por qué los videos actuales no sirven para georreferenciar

| Video | Hora local de inicio | Fin aproximado |
|---|---|---|
| `VID_20261108_110401.mp4` | 11:04:01 (-05:00) | 11:04:33 |
| `VID_20261108_111532.mp4` | 11:15:32 (-05:00) | 11:16:08 |

Los dos GPX empiezan a las 11:12:52 y 11:17:02 (hora local), fuera de esas ventanas.
La base `salidas/danos.db` referencia además un GPX que no está en esta copia:
`datos/gpx/20261108-110358.gpx`. Por eso las salidas actuales no tienen coordenadas
confiables y no se pueden validar contra campo.

## Fase por fase

### M1 — Datos

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Descargar RDD2022 y convertirla | Parcial | Solo está Japón; falta ejecutar `scripts/preparar_rdd2022.py` y decidir si se usan más países |
| Grabar 5 recorridos con video+GPX | Parcial | El CSV de `Prueba_region` demuestra 5 recorridos procesados, pero en disco solo están 2 videos y 2 GPX, y **ningún par coincide en tiempo**; faltan los videos `110956`, `111300`, `111705` y los GPX de estos videos |
| Extraer fotogramas y subirlos a Roboflow | Falta | No hay fotogramas extraídos ni proyecto/exportación local |
| Etiquetar 300–500 imágenes | Falta | No hay etiquetas propias; issue #4 |
| Exportar y combinar datasets | Falta | Faltan `datos/monteria/` y `datos/combinado/`; issues #5 y #6 |
| Verdad de campo y 10–20 huecos medidos | Falta | Faltan `datos/verdad_campo.csv` y `datos/huecos_medidos.csv` |

### M2 — Modelo

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Fase 1 con RDD2022 (`best_rdd.pt`) | Hecha | Métricas en [modelos/README.md](../modelos/README.md) y `reportes/modelo_test.md` |
| Fase 2 con dataset combinado (`best.pt`) | Bloqueada | No hay etiquetas ni dataset combinado; issue #10 |
| Comparar `n` contra `s` | Falta la comparación de precisión | La issue #26 midió fps con ambos; falta la comparación de métricas (issue #11) |
| Reporte de métricas | Parcial | Hay métricas de test de RDD2022 y curvas en `runs/`; falta evaluar en Montería |
| Publicar pesos y enlaces | Parcial | `best_rdd.pt` está local, pero no hay enlace directo en `modelos/README.md`; issue #13 |

Métricas conocidas de `best_rdd.pt`: mAP@0.5 de validación **0.643**, mAP@0.5 de
prueba **0.633**, mAP@0.5:0.95 de prueba **0.329**. El punto débil es D40 (huecos):
recall **0.445**, mAP@0.5 **0.505**; ver issue #47.

### M3 — Pipeline

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Etapas de entrada, YOLO, segmentación, medición, GPS, registro y salidas | Hecha | `src/tapahuecos/`; contratos en [contratos.md](contratos.md) |
| CLI y demo | Hecha | `tapahuecos` y `scripts/demo.py`; **115 pruebas** pasan |
| Prueba completa con un recorrido real | Parcial | Se procesaron videos sueltos y una corrida de humo de 60 fotogramas; falta una corrida verificable con video+GPX sincronizados |
| Área en m² | Bloqueada | No hay homografía ni `metros_por_pixel`; todas las salidas tienen `area_m2` vacío |
| Ajustar segmentación con recortes reales | Parcial | Hay trabajo previo en commits, pero faltan recortes revisados y métricas por clase |

Mejoras agregadas en esta rama para destrabar la operación:

- `tapahuecos verificar`: revisa Python, configuración, región, pesos, calibración,
  Ultralytics/PyTorch y, si se indican, video y GPX (incluido su solape temporal).
- `tapahuecos procesar --max-fotogramas N`: permite una prueba rápida sin procesar
  el video completo.
- `config.yaml` y `ConfigModelo.pesos` apuntan ahora a `modelos/best_rdd.pt` (fase 1)
  mientras no exista `best.pt`; así `procesar` funciona sin `--pesos` al instalar los
  pesos disponibles.

### Corrida de humo hecha en esta rama

Con `best_rdd.pt`, CPU (PyTorch 2.15.0+cpu), la región `0,0.43,1,0.65` y
`--cada 2`:

```text
60 fotogramas en 10.5 s (5.7 fps), 2 daños registrados (D40 y D10)
Video: salidas/smoke_region/VID_20261108_110401_anotado.mp4
```

Los dos daños quedaron sin GPS y sin área en m² (faltan GPX y calibración). Es una
prueba de que el pipeline corre de punta a punta, **no** una validación de campo:
los recortes son pequeños y deben revisarse como posibles falsos positivos. La salida
está en `salidas/smoke_region/` (ignorada por Git).

### M4 — Pruebas en campo

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Procesar todos los recorridos | Hecho en la revisión de campo, no reproducible en local | La issue #24 revisó 48 daños de 5 recorridos del 8/11/2026; solo 2 de esos videos están en esta copia |
| Revisar cada daño (`tapahuecos revisar`) | Hecho en la revisión de campo, no reproducible en local | Issue #24: 48/48 revisados, 37 reales, precisión 0.771 (D40 4/4, D20 30/39, D10 0/2). La BD revisada (`salidas/prueba_region/danos.db`) y `reportes/campo.md` no vienen en el ZIP; las 69 filas de las BD locales siguen sin `verificado` |
| Métricas de campo | Precisión hecha; recall pendiente | Precisión 0.771 según #24; el recall depende de la verdad de campo (#7) y no se midió |
| Medir fps con y sin GPU | Hecho en CPU; GPU pendiente | Issue #26: 805 fotogramas en 145.6 s (5.5 fps) sin región y 105.4 s (7.6 fps) con región, en CPU. No se midió con GPU porque el equipo no tiene NVIDIA |
| Error de área y posición | Bloqueada | Requiere homografía y `huecos_medidos.csv`; issue #27 |

### M5 — Entrega

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Corregir diapositiva 7 | Falta | No está el archivo de la presentación en esta copia |
| Informe final con métricas y capturas | Falta | Hay material base (métricas, curvas, mapas), pero no el informe final |
| Video de demostración | Parcial | Hay videos anotados antiguos; falta uno con un recorrido validado |
| Preparar sustentación | Falta | No hay documento de sustentación |
| Publicar release `v1.0` | Falta | No hay tags en el repositorio local |

## Qué falta traer del Drive (por prioridad)

1. **Etiquetas propias**: exportación de Roboflow (`datos/monteria/`) o el dataset
   combinado ya armado. Sin esto no se puede entrenar `best.pt` (fase 2).
2. **`modelos/best.pt`**, si ya se entrenó en Colab. Si no existe, la prioridad es el
   punto 1.
3. **Video de calibración** y/o `calibracion/homografia.npy`, más
   `datos/huecos_medidos.csv` con las mediciones con cinta. Sin esto no hay área en m²
   ni error de área/posición.
4. **Pares video+GPX sincronizados**: los 3 videos de recorrido que faltan
   (`110956`, `111300`, `111705`), el GPX de cada video (incluido
   `20261108-110358.gpx`, que referencia la BD actual) y el video de calibración si es
   el sexto video.
5. **Evidencia de campo**: `salidas/prueba_region/danos.db` (con `verificado`
   diligenciado) y `reportes/campo.md`, para reproducir la precisión 0.771 y calcular
   el recall cuando exista la verdad de campo.
6. **RDD2022 completo** si se van a usar más países; hoy solo está `Japan.zip`.

## Issues abiertas al 2026-11-11

Consultadas en GitHub; algunas tareas pueden estar implementadas pero la issue sigue
abierta porque falta la validación final:

- **M1:** #4, #5, #6.
- **M2:** #8, #10, #11, #12, #13, #15.
- **M3:** #14, #18, #19, #20, #21.
- **M4:** #17, #27, #47.
- **M5:** #29, #30, #31, #32.

La issue #21 (interfaz de consola) sigue pendiente de cámara física, Colab y revisión
en Windows, pero dos de sus hallazgos ya se atendieron en esta rama: `config.yaml`
apunta a `best_rdd.pt` mientras falta `best.pt`, y `modelos/README.md` ya tiene las
métricas y la ubicación de los pesos.

## Comandos para continuar

```bash
# 1. Comprobar el entorno y los insumos (no carga YOLO)
tapahuecos verificar --video datos/videos/VID_20261108_110401.mp4 \
  --gpx datos/gpx/20261108-111252.gpx --pesos modelos/best_rdd.pt

# 2. Instalar Ultralytics/PyTorch si el paso anterior lo reporta como error
pip install -e ".[yolo]"

# 3. Prueba real corta, sin GPX, para confirmar que el pipeline corre
tapahuecos procesar --video datos/videos/VID_20261108_110401.mp4 \
  --pesos modelos/best_rdd.pt --region 0,0.43,1,0.65 --max-fotogramas 60 \
  --salida salidas/smoke_region

# 4. Cuando haya un GPX que coincida, repetir sin --max-fotogramas y con --gpx
```

Nota: la región `0,0.43,1,0.65` es una aproximación para mirar solo la franja de la
vía en estos videos verticales; ajústela con los recortes antes de sacar métricas.
