# Datos (no versionados)

Esta carpeta está excluida de Git. Los archivos se comparten por la carpeta de Google Drive del equipo o por Roboflow.

```
datos/
├── videos/          VID_AAAAMMDD_HHMMSS.mp4 de los recorridos
├── gpx/             recorridos GPS grabados al mismo tiempo
├── RDD2022/         dataset descargado y descomprimido
├── rdd_yolo/        salida de scripts/preparar_rdd2022.py
├── monteria/        exportación de Roboflow (formato YOLOv8)
├── combinado/       salida de scripts/combinar_datasets.py
├── verdad_campo.csv latitud,longitud,clase de los daños anotados en campo
└── huecos_medidos.csv latitud,longitud,largo_m,ancho_m,area_m2,foto de los huecos medidos con cinta
```

Fuera de esta carpeta, y tampoco versionados:

- `modelos/`: pesos entrenados (`best_rdd.pt`, `best.pt`). Enlazarlos en `modelos/README.md`.
- `calibracion/`: `homografia.npy` y `vista_cenital.jpg`, generados por `scripts/calibrar_homografia.py`.
- `salidas/`: resultados de `tapahuecos procesar`.
