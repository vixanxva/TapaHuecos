# Guía de etiquetado (Roboflow)

Todos los integrantes deben etiquetar con los mismos criterios. Si no, el modelo aprende contradicciones.

## Proyecto en Roboflow

- Tipo: **Object Detection** (recuadros).
- Clases, escritas **exactamente** así: `D00`, `D10`, `D20`, `D40`. `scripts/combinar_datasets.py` descarta cualquier otro nombre.
- Exportación: formato **YOLOv8**, sin aumentos de datos (Ultralytics los aplica al entrenar).

## Qué imágenes subir

- Extraer 1 fotograma cada 1 o 2 segundos de los videos de Montería. Fotogramas consecutivos casi idénticos no aportan.
- Incluir **imágenes sin daños** (alrededor del 10 %): sombras de árboles, charcos sobre vía sana, parches ya reparados, tapas de alcantarilla, marcas viales. Son los falsos positivos más comunes.
- Todos los fotogramas de un mismo video van en la misma partición (train, valid o test). Así la evaluación no se infla.

## Criterios por clase

| Clase | Etiquetar | No etiquetar |
|---|---|---|
| **D00** Grieta longitudinal | Grieta paralela al sentido de la vía. Si es larga, un recuadro por tramo recto. | Juntas de construcción rectas entre losas de concreto. |
| **D10** Grieta transversal | Grieta que cruza la vía de lado a lado o en diagonal pronunciada. | Juntas transversales de pavimento rígido en buen estado. |
| **D20** Piel de cocodrilo | Área con malla de grietas; un recuadro que cubra toda la malla. | Una grieta aislada (es D00 o D10). |
| **D40** Hueco | Cavidad con pérdida de material, con o sin agua. Recuadro ajustado al borde del hueco. | Charcos sobre vía sana, sombras, parches de asfalto nuevo, tapas de alcantarilla. |

## Reglas generales

- Recuadros **ajustados** al daño, sin márgenes grandes de asfalto sano.
- No etiquetar daños tan lejanos o borrosos que no se puedan clasificar con seguridad.
- Si un hueco está dentro de una zona de piel de cocodrilo, se etiquetan los dos: el hueco como D40 y la zona como D20.
- Ante la duda, comentarlo en el issue de etiquetado antes de decidir. Las decisiones se anotan aquí para que queden como regla.
