# TapaHuecos — Detector de daños en las vías

Herramienta de consola en Python que recibe un video grabado desde un vehículo y su recorrido GPS, y entrega:

1. un **video anotado** con los daños de la vía (huecos y grietas);
2. una **carpeta con el recorte** de cada daño;
3. una **base de datos SQLite** con el tipo, el tamaño aproximado y la coordenada GPS de cada daño;
4. un **mapa HTML** con todos los puntos.

No es una app móvil ni una página web. Probado con videos de calles de Montería (Córdoba, Colombia).

```
Video (.mp4) + Recorrido GPS (.gpx)
   │
   ├─[1] Entrada ── lee 1 de cada N fotogramas
   ├─[2] YOLO ───── clase, confianza, recuadro e ID de seguimiento (ByteTrack)
   ├─[3] OpenCV ─── recorte → realce → máscara → contorno → área en px → área en m²
   ├─[4] GPS ────── hora del fotograma → posición interpolada en el GPX
   ├─[5] Registro ─ recorte .jpg + una fila en SQLite (una sola vez por daño)
   └─[6] Salidas ── video anotado + recortes + danos.db/danos.csv + mapa.html
```

## Clases detectadas (RDD2022)

| Código | Clase | Cómo se ve |
|---|---|---|
| D00 | Grieta longitudinal | Línea a lo largo del sentido de la vía |
| D10 | Grieta transversal | Línea perpendicular al sentido de la vía |
| D20 | Piel de cocodrilo | Red de grietas entrelazadas en forma de malla |
| D40 | Hueco | Cavidad con bordes definidos; suele verse más oscura o con agua |

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/vixanxva/TapaHuecos.git
cd TapaHuecos
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Linux/macOS: source .venv/bin/activate
pip install -e ".[yolo,dev]"
```

`[yolo]` instala Ultralytics (y PyTorch). Sin ese extra funcionan las pruebas y los comandos `mapa`, `exportar`, `resumen` y `revisar`.

## Uso rápido

```bash
# 1. (Una vez) calibrar la cámara para obtener áreas en m²
python scripts/calibrar_homografia.py --video datos/videos/calibracion.mp4 --ancho 3 --largo 5

# 2. Procesar un recorrido
tapahuecos procesar --video datos/videos/VID_20261029_143015.mp4 --gpx datos/gpx/20261029.gpx

# 3. Revisar los resultados
tapahuecos resumen
tapahuecos revisar          # marcar cada daño como real o falso positivo
python scripts/evaluar.py campo --db salidas/danos.db
python scripts/evaluar.py area --medidos datos/huecos_medidos.csv   # error de área y de posición
```

Todos los resultados quedan en `salidas/`: `*_anotado.mp4`, `recortes/`, `danos.db`, `danos.csv` y `mapa.html`. La base de datos acumula todos los recorridos procesados en esa carpeta.

| Comando | Qué hace |
|---|---|
| `tapahuecos procesar` | Procesa un video (`--video`) o la cámara en vivo (`--camara 0`). |
| `tapahuecos mapa` | Regenera el mapa HTML desde la base de datos (`--todos` para no agrupar repetidos). |
| `tapahuecos fusionar` | Agrupa el mismo daño registrado en varios recorridos (`--radio` en metros). |
| `tapahuecos exportar` | Exporta la base de datos a CSV. |
| `tapahuecos resumen` | Tabla de daños por clase. |
| `tapahuecos revisar` | Revisión manual de cada recorte (para las métricas de campo). |

Los parámetros (umbral de confianza, salto de fotogramas, zona horaria, segmentación, calibración) están en [config.yaml](config.yaml).

## Demo sin videos reales

Mientras no haya recorridos grabados, `scripts/demo.py` arma un video con imágenes de RDD2022 (prefiere las que tienen huecos etiquetados) y un GPX simulado por la Avenida Primera de Montería, para mostrar el sistema de punta a punta:

```bash
python scripts/demo.py --imagenes datos/rdd_yolo/images/test
tapahuecos procesar --video datos/demo/VID_AAAAMMDD_HHMMSS.mp4 --gpx datos/demo/VID_AAAAMMDD_HHMMSS_demo.gpx --pesos modelos/best_rdd.pt --salida salidas/demo
```

El script imprime el segundo comando con los nombres reales (`--help` muestra las opciones). Los resultados son de demostración, no de campo: las imágenes no son de Montería y el recorrido GPS es simulado.

## Entrenamiento

Se entrena en Google Colab (GPU T4 gratuita) en dos fases: primero con RDD2022 y luego un ajuste fino con fotos propias de Montería etiquetadas en Roboflow.

```bash
python scripts/preparar_rdd2022.py --origen datos/RDD2022 --destino datos/rdd_yolo
python scripts/entrenar.py --datos datos/rdd_yolo/data.yaml --destino modelos/best_rdd.pt
python scripts/combinar_datasets.py --entradas datos/rdd_yolo datos/monteria --destino datos/combinado --repetir 1 3
python scripts/entrenar.py --datos datos/combinado/data.yaml --modelo modelos/best_rdd.pt --epocas 50
python scripts/evaluar.py modelo --datos datos/combinado/data.yaml
```

## Estructura

```
TapaHuecos/
├── config.yaml                 parámetros del sistema
├── src/tapahuecos/
│   ├── entrada.py              [1] lectura de video y hora de inicio
│   ├── detector.py             [2] YOLO + ByteTrack
│   ├── segmentacion.py         [3] máscara del daño con OpenCV
│   ├── medicion.py             [3] área en m² por homografía
│   ├── gps.py                  [4] lectura del GPX e interpolación
│   ├── registro.py             [5] SQLite y registro único por daño
│   ├── salidas.py              [6] dibujo, video, mapa, CSV, resumen
│   ├── pipeline.py             orquesta las 6 etapas
│   ├── evaluacion.py           métricas de campo, error de área y de posición
│   ├── clases.py               D00, D10, D20, D40
│   └── cli.py                  comandos de consola
├── scripts/                    preparar datos, entrenar, evaluar, calibrar
├── tests/                      pruebas (no requieren YOLO ni GPU)
├── docs/                       documento técnico, guías y backlog
├── datos/  modelos/  calibracion/   (no versionados: ver datos/README.md)
└── .github/                    CI, plantillas de issues y de PR
```

## Documentación

- [Documento técnico](docs/documento_tecnico.md): alcance, arquitectura, cada etapa, métricas y riesgos.
- [Guía de captura](docs/guia_captura.md): cómo grabar el video y el GPX.
- [Guía de etiquetado](docs/guia_etiquetado.md): criterios para etiquetar en Roboflow.
- [Backlog](docs/backlog.md): issues e hitos del proyecto.
- [Cómo contribuir](CONTRIBUTING.md): ramas, commits y Pull Requests.

## Alcance

**Hace:** detectar cuatro tipos de daño en imágenes y video, resaltarlos y estimar su área, ubicarlos por GPS, registrarlos y mostrarlos en un mapa, y reportar métricas con videos reales.

**No hace:** medir la profundidad de los huecos (no es confiable con una sola cámara), procesar en tiempo real dentro del vehículo (el modo cámara funciona, pero a pocos fps en un portátil sin GPU), ni ofrecer interfaz gráfica, servidor web, app móvil o envío automático de reportes. Ver la sección 2 del [documento técnico](docs/documento_tecnico.md).
