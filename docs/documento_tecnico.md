# Detector de daños en las vías — Documento técnico

## 1. La idea en una frase

Un programa en Python que recibe un video grabado desde un vehículo y entrega cuatro cosas: un **video anotado** con los daños de la vía (huecos y grietas), una **carpeta con el recorte** de cada daño, una **base de datos** con su tipo, tamaño aproximado y coordenada GPS, y un **mapa HTML** con todos los puntos.

Es una herramienta de consola que funciona de principio a fin, y eso es exactamente lo que promete la presentación.

## 2. Alcance

### Dentro del alcance (lo que promete la presentación)

- Detectar automáticamente cuatro tipos de daño en imágenes y videos.
- Resaltar el daño con OpenCV y calcular su área aproximada.
- Asociar cada daño a una coordenada GPS y guardarlo en un registro.
- Mostrar los daños en un mapa.
- Probar el sistema con videos reales de calles de Montería y reportar métricas.

### Fuera del alcance (hay que declararlo explícitamente en la entrega)

| Tema | Motivo | Acción |
|---|---|---|
| **Profundidad del hueco** | Con una sola cámara no se puede medir de forma confiable. | La diapositiva 7 la menciona: corregirla o presentarla como trabajo futuro. |
| **Tiempo real en el vehículo** | El sistema procesa video ya grabado. El modo cámara en vivo funciona, pero a pocos fotogramas por segundo en un portátil sin GPU. | Presentarlo como procesamiento posterior al recorrido. |
| **Interfaz gráfica, servidor web o app móvil** | El producto es una herramienta de consola. | — |
| **Envío automático de reportes a las autoridades** | Fuera del tiempo del proyecto. | Trabajo futuro. |

## 3. Flujo completo

```
Video (.mp4) + Recorrido GPS (.gpx)
        │
        ▼
[1] ENTRADA ─── lee el video fotograma por fotograma (1 de cada N)
        │
        ▼
[2] YOLO ────── ¿hay daño? → clase, confianza, recuadro, ID de seguimiento
        │
        ▼
[3] OPENCV ──── recorta el recuadro → mejora la imagen → separa el daño
        │       → máscara binaria → contorno → área en px → área en m²
        ▼
[4] GPS ─────── hora del fotograma → busca en el GPX → latitud y longitud
        │
        ▼
[5] REGISTRO ── guarda el recorte (.jpg) + una fila en SQLite (una sola vez por daño)
        │
        ▼
[6] SALIDAS ─── video anotado + carpeta de recortes + base de datos + mapa.html
```

Cada etapa es un módulo de `src/tapahuecos/` (ver la sección 7) y `pipeline.py` las encadena.

## 4. Tecnologías

| Tecnología | Para qué se usa |
|---|---|
| **Python 3.10+** | Lenguaje de todo el proyecto. |
| **Ultralytics (YOLOv8 o YOLO11)** | Entrenar el detector y hacer inferencia. Incluye el seguimiento de objetos (ByteTrack) y el cálculo de métricas. |
| **OpenCV** (`opencv-python`) | Leer y escribir video, filtros, segmentación, contornos, homografía y dibujo del resultado. |
| **NumPy** | Operaciones sobre las imágenes, que son matrices. |
| **gpxpy** | Leer el archivo GPX que graba el celular. |
| **SQLite** (módulo `sqlite3`) | Base de datos en un solo archivo. Viene con Python; no hay que instalar nada. |
| **pandas** | Exportar el registro a CSV y analizar resultados. |
| **Folium** | Generar el mapa HTML interactivo. |
| **Google Colab** | GPU gratuita (Tesla T4) para entrenar. |
| **Roboflow** (plan gratuito) | Etiquetar las fotos propias y exportarlas en formato YOLO. |
| **Git + GitHub** | Repositorio, ramas, Pull Requests, issues, tablero de Projects e integración continua. |
| **App GPS del celular** | Grabar el recorrido en GPX mientras se graba el video (por ejemplo, GPS Logger en Android). |

### Relación con computación gráfica

Conviene mencionarla en la sustentación; cada concepto está en un punto concreto del código:

| Concepto | Dónde se usa |
|---|---|
| Espacios de color | Conversión BGR → escala de grises antes de segmentar (`segmentacion.py`). |
| Ecualización adaptativa del histograma (CLAHE) | Realce del contraste local del asfalto (`segmentacion.realzar`). |
| Filtros por convolución | Suavizado gaussiano para reducir el ruido de la textura del asfalto. |
| Umbralización (Otsu) | Separar el daño del fondo con un umbral calculado automáticamente. |
| Operaciones morfológicas | Apertura y cierre para limpiar la máscara; *black-hat* para resaltar grietas finas. |
| Contornos | Delimitar el daño y calcular su área. |
| Transformación proyectiva (homografía) | Llevar el contorno de la imagen al plano de la vía para medir en m² (`medicion.py`) y generar la vista cenital de calibración. |
| Composición alfa y dibujo | Máscara semitransparente, recuadros y etiquetas sobre el video (`salidas.py`). |

## 5. Cada etapa en detalle

### 5.1 Datos

**Clases.** Se usan las cuatro clases estándar del dataset RDD2022:

| Código | Clase | Cómo se ve |
|---|---|---|
| D00 | Grieta longitudinal | Línea a lo largo del sentido de la vía |
| D10 | Grieta transversal | Línea perpendicular al sentido de la vía |
| D20 | Piel de cocodrilo | Red de grietas entrelazadas en forma de malla |
| D40 | Hueco | Cavidad con bordes definidos; suele verse más oscura o con agua |

**Fuentes.**

1. **RDD2022** (*Road Damage Dataset 2022*): unas 47 000 imágenes de vías de Japón, India, República Checa, Noruega, Estados Unidos y China, anotadas en formato Pascal VOC. `scripts/preparar_rdd2022.py` lo convierte a formato YOLO, conserva solo las cuatro clases del proyecto (descarta D43, D44, D50 y otras), guarda un 10 % de imágenes sin daños como ejemplos negativos y lo divide en entrenamiento, validación y prueba (80/10/10). Las particiones de prueba oficiales no traen etiquetas, por eso las tres se generan a partir de la de entrenamiento.
2. **Fotos propias de Montería**: fotogramas extraídos de los videos de recorrido, etiquetados en Roboflow con los mismos códigos D00, D10, D20 y D40 (ver la [guía de etiquetado](guia_etiquetado.md)). Son pocas, pero enseñan al modelo cómo se ven las calles locales: otra textura de asfalto, pavimento rígido, agua estancada y sombras fuertes.

`scripts/combinar_datasets.py` une ambas fuentes, reordena las clases por nombre y permite sobremuestrear las fotos locales (`--repetir`).

**Regla para no inflar las métricas:** los fotogramas de un mismo video deben quedar todos en la misma partición. Si fotogramas casi idénticos quedan en entrenamiento y en prueba, las métricas salen artificialmente altas.

### 5.2 Entrenamiento

Se hace en Google Colab con `scripts/entrenar.py`, en dos fases:

1. **Base:** partir de los pesos preentrenados `yolov8s.pt` (o `yolo11s.pt`) y entrenar con RDD2022 → `modelos/best_rdd.pt`.
2. **Ajuste fino:** partir de `best_rdd.pt` y entrenar con el dataset combinado (Montería + RDD2022) → `modelos/best.pt`.

Parámetros iniciales: imágenes de 640 px, 100 épocas con parada temprana tras 20 épocas sin mejora, lote de 16. Se usa volteo horizontal, pero no rotación, porque la orientación distingue D00 de D10. Ultralytics guarda automáticamente las curvas de entrenamiento, la matriz de confusión y la curva precisión-exhaustividad; esas gráficas van al informe.

Los modelos `n` (nano) son más rápidos y los `s` (small), más precisos. Si el procesamiento en un portátil sin GPU resulta demasiado lento, se compara `n` contra `s` y se reporta el compromiso entre ambos.

### 5.3 Detección y seguimiento

`detector.py` llama a `model.track()` de Ultralytics, que combina YOLO con **ByteTrack**. Por cada fotograma entrega la clase, la confianza, el recuadro y un **ID de seguimiento** que se mantiene mientras el mismo daño siga a la vista. Ese ID permite registrar cada daño **una sola vez**, aunque aparezca en decenas de fotogramas seguidos.

Para ganar velocidad se procesa uno de cada N fotogramas (`video.cada_n_fotogramas`, 2 por defecto). El seguidor tolera ese salto.

**Región de interés.** En los videos grabados en vertical, la vía ocupa solo la parte inferior de la imagen; arriba hay cielo, árboles o edificios. Como YOLO reduce cada imagen a 640 px, analizar el fotograma completo hace que los huecos queden pequeños. Con `video.region` (por ejemplo, `[0, 0.45, 1, 1]`) YOLO analiza solo esa franja, así que los daños ocupan más píxeles y el procesamiento es más rápido. Los recuadros se devuelven en coordenadas del fotograma completo, por lo que la segmentación, la homografía y el registro no cambian. El video anotado muestra el borde de la región.

### 5.4 Segmentación y área

Dentro de cada recuadro, `segmentacion.py` separa los píxeles del daño:

1. Recorte del recuadro y conversión a escala de grises.
2. Realce: CLAHE y suavizado gaussiano.
3. Umbral según el tipo de daño:
   - **Hueco (D40):** región oscura y compacta → umbral de Otsu invertido, luego apertura y cierre.
   - **Grietas (D00, D10):** líneas finas → transformación *black-hat*, que resalta lo más oscuro y delgado que el elemento estructurante, y luego Otsu. No se aplica apertura, porque borraría la grieta.
   - **Piel de cocodrilo (D20):** como las grietas, más un cierre grande que une la malla en una sola región.
4. Contornos externos; se descartan los menores a `area_minima_px`.
5. Máscara binaria rellena → **área en píxeles**.

**De píxeles a m².** Por la perspectiva, un hueco lejano ocupa menos píxeles que uno cercano del mismo tamaño. Para corregirlo, `medicion.py` usa una **homografía** (una transformación proyectiva de la imagen al plano de la vía): cada contorno se proyecta al suelo y allí se mide su área en metros cuadrados. La homografía se calcula una sola vez con `scripts/calibrar_homografia.py`, marcando las cuatro esquinas de un rectángulo de medidas conocidas sobre la vía. El script guarda además una vista cenital para comprobar visualmente la calibración.

Limitaciones que hay que declarar:

- La homografía solo es válida si la cámara va **siempre en la misma posición** del vehículo y la vía es aproximadamente plana.
- Para las grietas, el área es la de los píxeles visibles de la grieta, así que es pequeña. Su longitud sería una medida más útil y queda como trabajo futuro.
- Si no hay calibración, el área se reporta solo en píxeles. `metros_por_pixel` es una alternativa aproximada que no corrige la perspectiva.

### 5.5 Georreferenciación

El celular graba el recorrido en un archivo GPX (un punto por segundo, cada uno con hora UTC) mientras la cámara graba el video. Para ubicar un fotograma:

1. **Hora de inicio del video.** Se toma, en este orden, del parámetro `--inicio` (o de `video.inicio_grabacion`), de la fecha en el nombre del archivo (`VID_20261029_143015.mp4` en Android, `PXL_20261029_143015123.mp4` en Pixel, `20261029_143015.mp4` en Samsung) o, como último recurso, de la fecha de modificación del archivo menos su duración. La hora local se convierte a UTC con `utc_offset_horas` (−5 en Colombia, que no tiene horario de verano).
2. **Hora del fotograma** = inicio + tiempo del fotograma + `desfase_gps_s`. Los celulares graban con tasa de fotogramas variable, así que `índice ÷ fps` se desfasa a lo largo de un video largo. Por eso se usa la marca de tiempo real de cada fotograma (`CAP_PROP_POS_MSEC`). Solo se vuelve a `índice ÷ fps` con cámaras en vivo o si la marca no es fiable (vale cero o deja de crecer).
3. **Posición:** interpolación lineal entre los dos puntos del GPX más cercanos en el tiempo (`gps.py`). Si el GPS dejó de registrar más de 30 s, o la hora cae fuera del recorrido, el daño se guarda sin coordenada en lugar de recibir una coordenada inventada.

Los videos de WhatsApp (`VID-20261029-WA0001.mp4`) traen la fecha pero no la hora, así que el nombre no sirve y hay que indicar `--inicio`.

**Rotación.** OpenCV ya gira el video según los metadatos de orientación del celular. Si el video llega girado de todos modos (no trae metadatos o la cámara se montó al revés), `video.rotacion` aplica un giro adicional de 90, 180 o 270 grados en sentido horario a cada fotograma. La calibración debe hacerse con el mismo giro (`calibrar_homografia.py --rotacion`).

El programa avisa si el video y el GPX no coinciden en el tiempo, que es el error más común (relojes desfasados o zona horaria mal configurada). La [guía de captura](guia_captura.md) explica cómo grabar ambos correctamente.

### 5.6 Registro

`registro.py` usa SQLite con dos tablas:

- **`recorridos`:** un registro por video procesado (video, GPX, modelo y fecha de procesamiento).
- **`danos`:** un registro por daño, con clase, confianza, veces que se vio, fotograma, segundo del video, hora UTC, latitud, longitud, área en px y en m², recuadro, ruta del recorte y un campo `verificado` para la revisión manual. La restricción `UNIQUE (recorrido_id, track_id)` garantiza un único registro por daño.

**Regla de registro único:** se agrupan las observaciones por ID de seguimiento. Cuando un daño deja de verse durante `max_ausencia` fotogramas, o cuando termina el video, se guarda **una vez**, con la observación de mayor confianza, siempre que haya aparecido en al menos `min_fotogramas` fotogramas. Esto descarta las detecciones espurias de un solo cuadro.

**Daños repetidos entre recorridos.** Si la misma calle se recorre varias veces, cada recorrido registra el mismo hueco. `fusion.py` agrupa los registros de la misma clase que están a menos de `radio_fusion_m` metros (8 m por defecto) y que provienen de recorridos distintos, y les asigna el mismo `grupo`. La agrupación se hace alrededor de semillas, sin encadenar, para que una grieta larga registrada por tramos no termine convertida en un único daño. El mapa y el resumen muestran daños únicos; la base de datos y el CSV conservan todos los registros.

### 5.7 Salidas

Todo queda en la carpeta de salida (`salidas/` por defecto):

| Archivo | Contenido |
|---|---|
| `<video>_anotado.mp4` | Video con la máscara semitransparente, el recuadro, la etiqueta (`D40 #12 0.87 0.15 m2`) y una cabecera con la hora y el GPS. Usa el códec `mp4v`; se reproduce con VLC. |
| `recortes/` | Un `.jpg` por daño, con su contorno dibujado. |
| `danos.db` | Base de datos SQLite. Acumula todos los recorridos procesados en esa carpeta. |
| `danos.csv` | La misma información, para Excel o pandas. |
| `mapa.html` | Mapa de OpenStreetMap con una capa por tipo de daño y un punto por daño único; al hacer clic en un punto se ven sus datos, su recorte y en cuántos recorridos se registró. |

## 6. Evaluación y métricas

Se reportan tres grupos de métricas, cada uno generado por un comando:

**1. Del modelo**, sobre la partición de prueba (`scripts/evaluar.py modelo`): precisión, exhaustividad (*recall*), F1, mAP@0.5 y mAP@0.5:0.95, por clase y en total, junto con la matriz de confusión. Hay que reportarlas por separado para la prueba de RDD2022 y para la de Montería.

**2. De campo**, sobre los recorridos reales de Montería (`tapahuecos revisar` y luego `scripts/evaluar.py campo`):

- **Precisión de campo:** de los daños registrados, qué fracción son reales (revisión manual de cada recorte).
- **Exhaustividad de campo:** se recorre a pie un tramo, se anota la coordenada de cada daño real en un CSV (`latitud,longitud,clase`) y se mide qué fracción tiene una detección a menos de 10 m.

**3. De funcionamiento:**

- **Velocidad:** fotogramas por segundo en el portátil del equipo, con y sin GPU. El programa la imprime al terminar.
- **Error de área:** se miden con cinta métrica entre 10 y 20 huecos y se compara su área real con la estimada (`scripts/evaluar.py area --medidos datos/huecos_medidos.csv`). El CSV tiene las columnas `latitud,longitud,largo_m,ancho_m,area_m2,foto`; si `area_m2` está vacía se toma la de una elipse, π/4 · largo · ancho. Cada hueco se empareja uno a uno con el D40 registrado más cercano a menos de 10 m (`--radio`), sin contar los marcados como falsos positivos, y se reportan la media, la mediana y el máximo de |estimada − real| / real, junto con una gráfica de área real contra estimada (si está instalado matplotlib).
- **Error de posición:** distancia entre la coordenada registrada y la real para esos mismos pares; el mismo comando reporta su media, mediana y máximo.

No se fija de antemano un valor objetivo de mAP. Se reporta lo obtenido y se compara con el modelo de la fase 1 (solo RDD2022), para mostrar cuánto aportan las fotos locales.

## 7. Estructura del repositorio

```
TapaHuecos/
├── config.yaml                 parámetros del sistema
├── src/tapahuecos/
│   ├── entrada.py              [1] lectura de video y hora de inicio
│   ├── detector.py             [2] YOLO + ByteTrack
│   ├── segmentacion.py         [3] máscara del daño
│   ├── medicion.py             [3] área en m² por homografía
│   ├── gps.py                  [4] GPX, interpolación y distancias
│   ├── registro.py             [5] SQLite y registro único por daño
│   ├── salidas.py              [6] dibujo, video, mapa, CSV y resumen
│   ├── pipeline.py             encadena las seis etapas
│   ├── evaluacion.py           métricas de campo
│   ├── clases.py               definición de D00, D10, D20 y D40
│   └── cli.py                  comandos procesar, mapa, exportar, resumen y revisar
├── scripts/
│   ├── preparar_rdd2022.py     VOC → YOLO, filtrado de clases y división
│   ├── combinar_datasets.py    une RDD2022 y Roboflow
│   ├── entrenar.py             entrenamiento y ajuste fino
│   ├── evaluar.py              métricas del modelo y de campo
│   └── calibrar_homografia.py  calibración píxeles → metros
├── tests/                      pruebas automáticas (no requieren YOLO ni GPU)
├── docs/                       este documento, guías y backlog
├── datos/ modelos/ calibracion/   no versionados (ver datos/README.md)
└── .github/                    CI y plantillas de issues y de Pull Request
```

## 8. Organización del trabajo en GitHub

- **Ramas:** `main` siempre funciona. Cada tarea se hace en una rama propia (`feature/…`, `fix/…`, `docs/…`) y entra a `main` por Pull Request, con al menos una revisión de otro integrante.
- **Issues:** una por tarea, con la plantilla del repositorio. El [backlog](backlog.md) trae la lista inicial, agrupada por hito.
- **Projects:** tablero con las columnas *Por hacer → En curso → En revisión → Hecho*.
- **Hitos (milestones):** M1 Datos · M2 Modelo · M3 Pipeline · M4 Pruebas en campo · M5 Entrega.
- **CI:** GitHub Actions ejecuta `ruff` y `pytest` en cada Pull Request.

Los detalles están en [CONTRIBUTING.md](../CONTRIBUTING.md).

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Pocas fotos locales etiquetadas | Partir de RDD2022 y sobremuestrear las fotos de Montería. |
| Confusión entre clases de grieta (D00, D10, D20) | Reportar la matriz de confusión; en el mapa todas siguen siendo daños útiles. |
| Desfase entre el reloj de la cámara y el GPS | Sincronizar los relojes antes de grabar, usar `desfase_gps_s` y el aviso de solapamiento. |
| Vibración y desenfoque por movimiento | Soporte firme, velocidad baja (< 30 km/h) y buena luz. |
| Sombras, agua y parches confundidos con huecos | Incluir esos casos como negativos al etiquetar; revisión manual en campo. |
| Área poco confiable | Calibrar con la cámara fija, declarar el error medido y no prometer la profundidad. |
| Colab corta la sesión | Guardar los pesos en Google Drive; Ultralytics permite reanudar (`resume=True`). |
| Archivos pesados en Git | `.gitignore` excluye datos y modelos; se comparten por Drive o Roboflow. |

## 10. Trabajo futuro

- Estimar la profundidad (cámara estéreo, LiDAR del celular o sensor de profundidad).
- Longitud y ancho de las grietas (esqueletización de la máscara).
- Procesamiento en tiempo real con un modelo exportado a ONNX o TensorRT en un dispositivo con GPU.
- Lectura automática de la hora de inicio desde los metadatos del video (ffprobe) y de la telemetría GPS incrustada en cámaras de acción.
- App móvil o web para consultar el mapa y envío de reportes a la Alcaldía de Montería.
- Priorización de reparaciones por severidad, tamaño y tráfico de la vía.
