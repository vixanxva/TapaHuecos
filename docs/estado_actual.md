# Estado actual del proyecto

Fecha de corte: **2026-11-11**. Rama local `avance-local`, creada desde `develop`
(`29148c0`), con tres commits locales y **sin rama remota configurada**.

Este documento resume qué hay realmente en esta copia local, qué falta para cada hito
del [backlog](backlog.md) y cuál es el siguiente paso verificable. El inventario se
rehízo leyendo los archivos y los ZIP, no la instantánea anterior. No reemplaza las
issues de GitHub: cuando una tarea existe allí, se indica su número.

## Resumen

- El código del pipeline está completo y la suite pasa: **115 pruebas**.
- Los **seis videos** y los **seis GPX** de la campaña están en disco. Cinco videos
  tienen un GPX que los cubre de principio a fin; el sexto (`125447`) no tiene GPX.
- RDD2022 está completo para el plan del notebook: **cinco ZIP de países**
  (`Japan`, `India`, `Czech`, `United_States`, `China_MotorBike`). Falta convertirlo
  a `datos/rdd_yolo/`.
- La fase 1 del modelo está disponible (`modelos/best_rdd.pt`, 22.5 MB).
  `runs/rdd_completo/weights/best.pt` es **el mismo checkpoint de fase 1**, no un
  modelo de fase 2.
- La base revisada `Salidas/Prueba_region/danos.db` tiene **48/48 daños revisados:
  39 reales y 9 falsos positivos**; precisión **0.8125**. No hay verdad de campo, así
  que la exhaustividad sigue sin medirse.
- La app Android compañera está en `android/`, compila y pasa sus pruebas unitarias y
  Lint, pero **todavía no se ha probado en un teléfono físico**.
- Los bloqueos reales ya no son “faltan videos”: son **etiquetas propias**,
  **`best.pt` de fase 2**, **calibración**, **verdad de campo/mediciones con cinta** y
  **trabajo humano de entrega** (informe, demo, sustentación, release).

## Inventario local

| Insumo | Estado | Detalle |
|---|---|---|
| Videos | Completo | `datos/videos/`: seis `.mp4` 1080x1920, de 32.4 a 58.2 s. Todos se decodifican completos |
| GPX | Completo para cinco recorridos | `datos/gpx/`: cinco GPX cubren sus videos con 3–11 s de margen al inicio. `20261108-110219.gpx` es un recorrido de 46 s sin video; `VID_20261108_125447.mp4` no tiene GPX |
| Pares video+GPX | Cinco verificados | `110401↔110358`, `110956↔110953`, `111300↔111252`, `111532↔111521`, `111705↔111702` |
| RDD2022 | Completo para el plan | `datos/RDD2022/`: `Japan.zip`, `India.zip`, `Czech.zip`, `United_States.zip`, `China_MotorBike.zip` (2.49 GB en total) |
| RDD2022 en formato YOLO | Falta | No existe `datos/rdd_yolo/`; hay que ejecutar `scripts/preparar_rdd2022.py` |
| Dataset propio | Falta | No hay `datos/monteria/` (Roboflow) ni `datos/combinado/` |
| Pesos fase 1 | Disponible | `modelos/best_rdd.pt`, 22,530,474 bytes, SHA-256 `15B5169A…3AFB5`; `runs/rdd_completo/weights/best.pt` es idéntico |
| Pesos fase 2 | Falta | No hay `modelos/best.pt` |
| Calibración | Falta | `calibracion/` solo tiene `.gitkeep`; no hay video de calibración ni `homografia.npy` |
| Verdad de campo | Falta | No hay `datos/verdad_campo.csv` ni `datos/huecos_medidos.csv` |
| Salidas revisadas | Disponible | `Salidas/Prueba_region/danos.db`: 48 daños de cinco recorridos, 48 revisados, 39 reales; incluye videos anotados, 48 recortes, `danos.csv` y `mapa.html` |
| Otras salidas | Parciales, sin revisar | `Salidas/danos.db` (15 daños) y `Salidas/fps_prueba/danos.db` (6), sin `verificado`; `Salidas/prueba_default/danos.db` está vacía |
| Reporte de campo | Actualizado | `reportes/campo.md`/`.json`: 48 revisados, 39 reales, precisión 0.8125; exhaustividad y F1 sin dato |
| Reporte de modelo | Disponible | `reportes/modelo_test.md`/`.json` y curvas/matriz en `runs/rdd_completo/` |
| App Android | Compila, sin probar en hardware | `android/`; APK en `android/app/build/outputs/apk/debug/app-debug.apk`; ver [android/README.md](../android/README.md) |
| ZIP de Drive | Conservados | `drive-download-20261111T215651Z-1-00{1,2,3}.zip`, 5.17 GB en total; no se modificaron ni se borraron |

## Videos y GPX verificados

Se decodificaron los seis videos completos con OpenCV y se leyeron las horas de los
`<trkpt>` del GPX (no la hora de metadatos del archivo).

| Video | Resolución / fps | Duración | Fotogramas | GPX | Margen del GPX | Resultado |
|---|---|---|---|---|---|---|
| `VID_20261108_110401.mp4` | 1080x1920 / 49.6 | 32.4 s | 1609/1609 | `20261108-110358.gpx` | empieza 3 s antes, termina 4 s después | Cubierto |
| `VID_20261108_110956.mp4` | 1080x1920 / 56.2 | 58.2 s | 3268/3268 | `20261108-110953.gpx` | 3 s antes, 7 s después | Cubierto |
| `VID_20261108_111300.mp4` | 1080x1920 / 53.0 | 38.2 s | 2027/2027 | `20261108-111252.gpx` | 8 s antes, 4 s después | Cubierto |
| `VID_20261108_111532.mp4` | 1080x1920 / 49.6 | 36.2 s | 1796/1796 | `20261108-111521.gpx` | 11 s antes, 4 s después | Cubierto |
| `VID_20261108_111705.mp4` | 1080x1920 / 47.3 | 39.5 s | 1868/1868 | `20261108-111702.gpx` | 3 s antes, 5 s después | Cubierto |
| `VID_20261108_125447.mp4` | 1080x1920 / 50.0 | 40.5 s | 2027/2027 | — | — | Sin GPX |

Los cinco videos de la campaña tienen metadatos de rotación de 90°; el sexto, 0°.
La diferencia máxima entre el tiempo por `CAP_PROP_POS_MSEC` y `índice / fps` llegó a
**2.03 s**, por encima del umbral de 1 s de la issue #14. El código ya usa
`CAP_PROP_POS_MSEC` y solo cae a `índice / fps` si la marca no es fiable
(`src/tapahuecos/entrada.py`), así que no hizo falta cambiar nada.

## Fase por fase

### M1 — Datos

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Descargar RDD2022 y convertirla | Descarga hecha; conversión pendiente | Están los cinco ZIP del plan; falta ejecutar `scripts/preparar_rdd2022.py` para crear `datos/rdd_yolo/` |
| Grabar 5 recorridos con video+GPX | Hecho | Cinco pares verificados; el sexto video no tiene GPX |
| Extraer fotogramas y subirlos a Roboflow | Falta | No hay fotogramas extraídos ni proyecto/exportación local; requiere cuenta de Roboflow |
| Etiquetar 300–500 imágenes | Falta | No hay etiquetas propias; issue #4/#5, trabajo humano |
| Exportar y combinar datasets | Bloqueada | Falta `datos/monteria/`; sin él no se puede crear `datos/combinado/` |
| Verdad de campo y 10–20 huecos medidos | Falta | Faltan los dos CSV; requiere medición con cinta en campo |

### M2 — Modelo

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Fase 1 con RDD2022 (`best_rdd.pt`) | Hecha | Métricas en [modelos/README.md](../modelos/README.md) y `reportes/modelo_test.md` |
| Fase 2 con dataset combinado (`best.pt`) | Bloqueada | No hay etiquetas ni dataset combinado; issue #10 |
| Comparar `n` contra `s` | Bloqueada | Faltan los dos entrenamientos y la prueba de Montería; issue #11 |
| Reporte de métricas | Parcial | RDD2022 hecho; falta evaluar en la prueba de Montería; issue #12 |
| Publicar pesos y enlaces | Parcial | `best_rdd.pt` está local y documentado; falta un enlace público o release; issue #13 |

Métricas conocidas de `best_rdd.pt`: mAP@0.5 de validación **0.643**, mAP@0.5 de
prueba **0.633**, mAP@0.5:0.95 de prueba **0.329**. El punto débil es D40 (huecos):
recall **0.445**, mAP@0.5 **0.505**; ver issue #47.

### M3 — Pipeline

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Etapas de entrada, YOLO, segmentación, medición, GPS, registro y salidas | Hecha | `src/tapahuecos/`; contratos en [contratos.md](contratos.md) |
| CLI y demo | Hecha | `tapahuecos` y `scripts/demo.py`; **115 pruebas** pasan |
| Prueba completa con un recorrido real | Hecha en esta revisión | Se procesó `110401` con su GPX y la franja de vía; los daños quedaron con coordenadas |
| Área en m² | Bloqueada | No hay homografía ni `metros_por_pixel`; las salidas tienen `area_m2` vacío |
| Ajustar segmentación con recortes reales | Parcial | Hay recortes revisados de la campaña, pero sin métricas por clase |

### M4 — Pruebas en campo

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Procesar todos los recorridos | Hecho | La campaña procesó cinco recorridos; la BD y los videos anotados están en `Salidas/Prueba_region/` |
| Revisar cada daño (`tapahuecos revisar`) | Hecho | 48/48 revisados: 39 reales y 9 falsos. Por clase: D00 3/3, D10 0/2, D20 32/39, D40 4/4 |
| Métricas de campo | Precisión hecha; exhaustividad pendiente | Precisión **0.8125** (39/48). Sin `verdad_campo.csv` no se puede medir recall ni F1 |
| Medir fps con y sin GPU | Hecho en CPU; GPU no disponible | Issue #26: 805 fotogramas en 145.6 s (5.5 fps) sin región y 105.4 s (7.6 fps) con región, en CPU |
| Error de área y posición | Bloqueada | Requiere homografía y `huecos_medidos.csv`; issue #27 |

### M5 — Entrega

| Tarea | Estado | Qué falta / evidencia |
|---|---|---|
| Corregir diapositiva 7 | Falta | No está la presentación en esta copia |
| Informe final | Falta | Hay material base (métricas, curvas, mapas), pero no el informe |
| Video de demostración | Parcial | Hay videos anotados; falta convertirlos a H.264 y grabar la demo |
| Preparar sustentación | Falta | No hay documento de sustentación |
| Publicar release `v1.0` | Falta | No hay tags y el release necesita `best.pt` e informe |

## Verificaciones hechas en esta rama

### Videos, GPX y hora de inicio (#14)

- Los seis videos abren y se decodifican completos (1609 a 3268 fotogramas).
- Los cinco pares video+GPX se solapan; el GPX empieza antes y termina después del
  video en todos los casos.
- La hora de inicio se deduce correctamente del nombre `VID_AAAAMMDD_HHMMSS` y el
  desplazamiento UTC es −5.
- La marca de tiempo del video se toma de `CAP_PROP_POS_MSEC`; la deriva observada
  justifica no usar `índice / fps`.
- La rotación de 90° se corrige automáticamente.
- Todos los videos de la campaña son `.mp4`; no hay `.MOV` ni H.265 en esta copia, así
  que ese punto de la issue #14 queda sin probar.

### Georreferenciación con un recorrido real (#18)

Se procesó el par `VID_20261108_110401.mp4` ↔ `20261108-110358.gpx` con la franja de
vía (`--region 0,0.45,1,1`):

```text
805 fotogramas en 151.2 s (5.3 fps), 5 daños registrados
```

Los cinco daños quedaron con hora UTC dentro del GPX y coordenada sobre la polilínea
interpolada (error de interpolación 0.00–0.01 m). El mapa generado tiene 5 marcadores
y 5 popups, y los 5 recortes existen. Esto valida la interpolación y el flujo
video+GPX; **no** demuestra el criterio de 10 m contra la posición real, porque para
eso falta la verdad de campo (#7). La salida está en `salidas/validacion_gpx_110401/`
(ignorada por Git).

### Salidas (#20)

Sobre `Salidas/Prueba_region/`:

- `danos.csv`: 48 filas, 22 columnas, UTF-8 con BOM, tildes correctas y ningún
  recorte faltante.
- `mapa.html`: 48 marcadores, 48 popups, capa por clase y 48 imágenes de recorte
  enlazadas.
- Los cinco videos anotados abren y tienen imagen; son 1080x1920 con códec `FMP4`
  (`mp4v`). Para la presentación falta convertirlos a H.264.
- La base tiene coordenadas en las 48 filas.

### Notebook de Colab (#8)

`notebooks/entrenamiento_colab.ipynb` tiene 26 celdas; las 13 de código pasan la
comprobación de sintaxis. Cubre GPU, Drive, clonado, descarga de RDD2022, conversión,
Roboflow opcional, entrenamiento, reanudación, evaluación y descarga del modelo. No se
ejecutó en Colab en esta sesión (requiere GPU y cuenta de Google).

### Fusión de daños (#19)

Sobre una copia de `Salidas/Prueba_region/danos.db`, `tapahuecos fusionar --radio 8`
dejó **48 registros en 48 daños únicos**. No hubo fusiones porque los cinco recorridos
son tramos consecutivos de la misma salida, no pasadas repetidas por la misma calle.
La funcionalidad y sus pruebas ya existen; falta el conteo manual para el criterio del
15 %.

### App Android

- `assembleDebug testDebugUnitTest lintDebug`: compila, las pruebas unitarias pasan y
  Lint queda con **0 errores** (solo avisos de versiones).
- APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Pendiente: instalarla en un teléfono real, grabar con la pantalla apagada y
  comprobar que el GPX exportado se procesa con el pipeline.

## Issues abiertas al 2026-11-11

Se consultaron las 22 issues abiertas. **No hay credenciales de GitHub en este
entorno**, así que no se pueden comentar, cerrar ni publicar releases desde aquí. Esta
es la situación verificable de cada una:

| Issue | Estado local | Qué falta para cerrarla |
|---|---|---|
| #1 Configurar repositorio | Bloqueada | Colaboradores, tablero, protección de `main`, reparto: configuración humana en GitHub |
| #4 Extraer fotogramas y subirlos | Bloqueada | Extraer localmente es posible, pero la subida y la partición requieren cuenta de Roboflow |
| #5 Etiquetar 300–500 imágenes | Bloqueada | Trabajo humano de etiquetado y revisión cruzada |
| #6 Exportar y combinar datasets | Bloqueada | Falta `datos/monteria/`; RDD2022 ya está descargado |
| #8 Notebook de Colab | Implementado | El notebook existe y cubre las celdas pedidas; falta la prueba de 1 época en Colab |
| #10 Fase 2 (`best.pt`) | Bloqueada | Faltan etiquetas y dataset combinado |
| #11 Comparar `n` contra `s` | Bloqueada | Depende de #10 y de la prueba de Montería |
| #12 Reporte de métricas | Parcial | RDD2022 hecho (`reportes/modelo_test.*`); falta la prueba de Montería |
| #13 Publicar pesos | Parcial | Fase 1 documentada con SHA-256; falta enlace público/release y `best.pt` |
| #14 Validar video y hora | Verificada en los `.mp4` de la campaña | Falta probar `.MOV`/H.265 y comentar/cerrar en GitHub |
| #15 Validar detección con `best.pt` | Bloqueada | No existe `best.pt` |
| #17 Calibrar cámara y área | Bloqueada | Falta video de calibración y `homografia.npy` |
| #18 Validar georreferenciación | Parcial | Interpolación y mapa verificados; falta verdad de campo para el criterio de 10 m |
| #19 Registro único y fusión | Implementado | La fusión existe y tiene pruebas; falta el conteo manual del 15 % |
| #20 Revisar video, mapa y CSV | Verificada localmente | Falta H.264 y revisión en los equipos de todos los integrantes |
| #21 Probar CLI en Windows y Colab | Parcial | Ayuda, errores y `verificar` revisados en Windows; faltan cámara, Colab y otros equipos |
| #27 Error de área y posición | Bloqueada | Faltan calibración y `huecos_medidos.csv` |
| #29 Informe final | Bloqueada | Trabajo humano |
| #30 Video de demostración | Bloqueada | Trabajo humano; requiere elegir el tramo y convertir a H.264 |
| #31 Sustentación | Bloqueada | Trabajo humano |
| #32 Release `v1.0` | Bloqueada | Depende de #13, #29 y de credenciales para publicar |
| #47 Mejorar D40 | Bloqueada | Faltan ejemplos etiquetados y el ajuste fino; no se arregla con umbrales |

## Qué falta hacer, por prioridad

1. **Etiquetar las fotos de Montería** y exportar `datos/monteria/`; sin esto no hay
   fase 2 ni comparación `n`/`s`.
2. **Entrenar y publicar `best.pt`**; después repetir la prueba de D40 (#47) y elegir
   el umbral con datos (#15).
3. **Calibrar la cámara** y medir 10–20 huecos con cinta; sin esto no hay área en m²
   ni error de área/posición (#17, #27).
4. **Levantar la verdad de campo** de un tramo y contar a mano los daños; así se
   calculan exhaustividad/F1 (#18) y se valida la fusión (#19).
5. **Probar la app Android en un teléfono** y procesar su GPX con el pipeline.
6. **Cerrar la entrega**: convertir los videos anotados a H.264, informe, demo,
   sustentación y release.

## Comandos para continuar

```bash
# 1. Comprobar un par real (no carga YOLO)
tapahuecos verificar --video datos/videos/VID_20261108_110401.mp4 \
  --gpx datos/gpx/20261108-110358.gpx --pesos modelos/best_rdd.pt

# 2. Procesar el recorrido completo con su GPX
tapahuecos procesar --video datos/videos/VID_20261108_110401.mp4 \
  --gpx datos/gpx/20261108-110358.gpx --region 0,0.45,1,1 \
  --salida salidas/validacion_gpx_110401

# 3. Regenerar las métricas de campo desde la base revisada
python scripts/evaluar.py campo --db Salidas/Prueba_region/danos.db

# 4. Intentar la fusión sobre una copia de la base, no sobre la original
copy Salidas\Prueba_region\danos.db %TEMP%\danos_fusion.db
tapahuecos fusionar --db %TEMP%\danos_fusion.db --radio 8

# 5. Compilar y probar la app Android
cd android && ./gradlew assembleDebug testDebugUnitTest lintDebug
```

Nota: la región `0,0.45,1,1` es una aproximación para la franja de la vía en estos
videos verticales; ajústela con los recortes antes de sacar métricas.
