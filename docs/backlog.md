# Backlog del proyecto

Lista inicial de issues para el tablero de GitHub Projects, agrupada por hito. Cada línea se convierte en una issue con la plantilla **Tarea**. ☑ indica que ya existe una primera versión en el repositorio, que el equipo debe probar y ajustar con datos reales.

## M1 · Datos

- [ ] Descargar RDD2022 y convertirlo con `scripts/preparar_rdd2022.py`
- [ ] Grabar al menos 5 recorridos en Montería (video + GPX), siguiendo la [guía de captura](guia_captura.md)
- [ ] Extraer fotogramas de los recorridos y subirlos a Roboflow
- [ ] Etiquetar entre 300 y 500 imágenes locales según la [guía de etiquetado](guia_etiquetado.md)
- [ ] Exportar el dataset de Roboflow y combinarlo con `scripts/combinar_datasets.py`
- [ ] Levantar la verdad de campo de un tramo (CSV `latitud,longitud,clase`) y medir 10–20 huecos con cinta métrica

## M2 · Modelo

- [ ] Fase 1: entrenar con RDD2022 en Colab (`yolov8s`) → `best_rdd.pt`
- [ ] Fase 2: ajuste fino con el dataset combinado → `best.pt`
- [ ] Comparar `n` contra `s` en precisión y velocidad
- [ ] Generar el reporte de métricas del modelo (`scripts/evaluar.py modelo`) para RDD2022 y para Montería
- [ ] Guardar los pesos finales en Drive y enlazarlos en `modelos/README.md`

## M3 · Pipeline

- ☑ Lectura de video y hora de inicio (`entrada.py`)
- ☑ Detección y seguimiento (`detector.py`)
- ☑ Segmentación con OpenCV (`segmentacion.py`): ajustar parámetros con recortes reales
- ☑ Calibración y área en m² (`medicion.py`, `scripts/calibrar_homografia.py`)
- ☑ Georreferenciación con GPX (`gps.py`)
- ☑ Registro en SQLite, una sola vez por daño (`registro.py`)
- ☑ Video anotado, mapa, CSV y resumen (`salidas.py`)
- ☑ Interfaz de consola (`cli.py`)
- ☑ Demo sin videos reales: video con imágenes de RDD2022 y GPX simulado en Montería (`scripts/demo.py`)
- [ ] Probar el pipeline completo con un recorrido real y corregir lo que falle

## M4 · Pruebas en campo

- [ ] Procesar todos los recorridos de Montería
- [ ] Revisar cada daño registrado (`tapahuecos revisar`)
- [ ] Calcular las métricas de campo (`scripts/evaluar.py campo --verdad …`)
- [ ] Medir los fps en el portátil del equipo, con y sin GPU
- [ ] Calcular el error de área y el error de posición contra las mediciones con cinta métrica

## M5 · Entrega

- [ ] Corregir la diapositiva 7: la profundidad pasa a trabajo futuro
- [ ] Informe final con métricas, gráficas de entrenamiento y capturas del mapa
- [ ] Video de demostración (video anotado + mapa)
- [ ] Preparar la sustentación, incluida la relación con computación gráfica (sección 4 del documento técnico)
- [ ] Publicar el release `v1.0` en GitHub
