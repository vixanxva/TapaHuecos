# Recortes reales para las pruebas de segmentación

Recortes pequeños (1–13 KB) usados por `tests/test_segmentacion.py` como pruebas de regresión. Son la única excepción a la regla de no subir imágenes al repositorio.

## Fuente

Recuadros etiquetados a mano en la partición de prueba de **RDD2022**, recortados con la caja exacta de la etiqueta y guardados en JPEG (calidad 92):

> Arya, D.; Maeda, H.; Sekimoto, Y.; Omata, H.; Ghosh, S. K.; Toshniwal, D.; et al. (2022). *RDD2022 - The multi-national Road Damage Dataset released through CRDDC'2022*. figshare. Dataset. https://doi.org/10.6084/m9.figshare.21431547.v1

Artículo de los datos: Arya, D. et al. *RDD2022: A multi-national image dataset for automatic road damage detection*. Geoscience Data Journal 11(4), 846–862 (2024). https://doi.org/10.48550/arXiv.2209.08538

| Archivo | Imagen original | Clase | Caso |
|---|---|---|---|
| `d40_hueco_claro_japan_012290.jpg` | `Japan_012290` | D40 | hueco más claro que el asfalto |
| `d40_hueco_claro_pequeno_japan_010295.jpg` | `Japan_010295` | D40 | hueco claro en un recorte de 43 × 26 px |
| `d40_hueco_con_agua_india_003761.jpg` | `India_003761` | D40 | hueco con agua |
| `d40_hueco_delgado_japan_011590.jpg` | `Japan_011590` | D40 | hueco oscuro y delgado |
| `d00_grieta_larga_us_000575.jpg` | `United_States_000575` | D00 | grieta larga sobre asfalto oscuro |
| `d00_grieta_japan_006566.jpg` | `Japan_006566` | D00 | grieta poco contrastada |
| `d10_grieta_gruesa_japan_005615.jpg` | `Japan_005615` | D10 | grieta gruesa |
| `d10_grieta_marcas_viales_us_000919.jpg` | `United_States_000919` | D10 | grieta junto a marcas viales |

## Licencia

El registro de RDD2022 en figshare indica [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). El README del repositorio de los autores (https://github.com/sekilab/RoadDamageDetector) indica [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) para las imágenes. Para cumplir las dos, estos recortes (una adaptación: se recortaron y se volvieron a codificar) se distribuyen bajo **CC BY-SA 4.0**, con la atribución de arriba.

Esta licencia cubre solo las imágenes de esta carpeta. El resto del repositorio mantiene su propia licencia (ver `LICENSE`).
