# Diapositivas de la sustentación

Esqueleto listo para copiar a Google Slides o PowerPoint. Cada `---` separa una
diapositiva; se indica el título, lo que va escrito y una nota de lo que se dice (el guion
completo está en [presentacion.md](presentacion.md)). Apuntes para el público: no más de
6 líneas por diapositiva y una imagen grande.

---

## [1] Portada

**TapaHuecos** — Detección automática de daños en las vías a partir de video y GPS

- Detector de huecos y grietas con YOLO + OpenCV
- Recorridos reales en Montería (Córdoba, Colombia)
- Curso / asignatura · Integrantes · Fecha
- `github.com/vixanxva/TapaHuecos`

*Nota:* diapositiva de 15 segundos. Mientras se muestra, se abre el navegador con la
interfaz web ya lista.

---

## [2] El problema

- Las vías de Montería tienen huecos, grietas y piel de cocodrilo.
- Hoy se inspeccionan **a ojo**, recorriéndolas a pie o en moto, con planillas de papel.
- No hay un inventario con **ubicación** y **tamaño** de cada daño.
- Sin ese inventario es difícil priorizar las reparaciones.

*Nota:* una foto de una calle con huecos vale más que las cuatro líneas.

---

## [3] La idea

> Recorrer la calle grabando video con el celular y su recorrido GPS.
> Después, un programa revisa el video y entrega un **mapa** con cada daño.

- Una sola pasada en el vehículo sustituye la inspección a pie.
- El resultado es un inventario, no una impresión.

---

## [4] Qué entrega el sistema

De **un video y su GPX** salen cuatro cosas:

1. **Video anotado** con cada daño marcado y etiquetado.
2. **Recorte** en imagen de cada daño.
3. **Base de datos** (SQLite y CSV) con tipo, tamaño aproximado y coordenada.
4. **Mapa interactivo** con un punto por daño y su recorte.

*Nota:* aquí se muestra una captura real del mapa (`salidas/campana_20261108/mapa.html`) y un
fotograma del video anotado.

---

## [5] Cómo funciona: seis etapas

```
Video (.mp4) + Recorrido GPS (.gpx)
        │
[1] ENTRADA ── lee 1 de cada N fotogramas
        │
[2] YOLO ───── clase, confianza, recuadro, ID de seguimiento
        │
[3] OPENCV ─── recorte → realce → máscara → contorno → área en px y en m²
        │
[4] GPS ────── hora del fotograma → posición interpolada en el GPX
        │
[5] REGISTRO ─ recorte .jpg + una fila en SQLite (una sola vez por daño)
        │
[6] SALIDAS ── video anotado + recortes + danos.db + danos.csv + mapa.html
```

*Nota:* es la diapositiva que más se va a mirar. Recorrerla en 60 segundos, nombrando solo
las etapas.

---

## [6] Los datos

**Base pública (RDD2022):** ~47 000 imágenes de vías de Japón, India, República Checa,
Noruega, Estados Unidos y China, ya etiquetadas con las cuatro clases del proyecto.

| Código | Clase |
|---|---|
| D00 | Grieta longitudinal |
| D10 | Grieta transversal |
| D20 | Piel de cocodrilo |
| D40 | Hueco |

**Datos propios:** 6 recorridos grabados en Montería con video y recorrido GPS.
Cinco de ellos con su GPX sincronizado.

*Nota:* declarar sin rodeos que **las fotos propias todavía no están etiquetadas** y que por
eso el modelo entregado es el entrenado con RDD2022. Es un insumo listo, no un pendiente
oculto.

---

## [7] El modelo

**YOLOv8s** entrenado en Google Colab (GPU T4), 85 épocas sobre RDD2022.

| Clase | Precisión | Exhaustividad | mAP@0.5 |
|---|---|---|---|
| D00 Grieta longitudinal | 0.664 | 0.670 | 0.706 |
| D10 Grieta transversal | 0.634 | 0.572 | 0.613 |
| D20 Piel de cocodrilo | 0.692 | 0.648 | 0.708 |
| **D40 Hueco** | 0.624 | **0.445** | **0.505** |
| **Total** | 0.654 | 0.584 | **0.633** |

- ~9,7 ms por imagen en GPU; 5,3–7,6 fotogramas/s en un portátil sin GPU.
- El punto débil es **D40 (huecos)**: coincide con la observación de campo.

*Nota:* explicar en una frase qué es el mAP («qué tan bien acierta, de 0 a 1»).

---

## [8] Computación gráfica: dónde se usa

| Concepto | Para qué |
|---|---|
| Espacios de color | Pasar de color a escala de grises antes de analizar |
| CLAHE | Realzar el contraste local del asfalto |
| Convolución | Suavizar el ruido de la textura del pavimento |
| Umbral de Otsu | Separar el daño del fondo automáticamente |
| Morfología | Limpiar la máscara y resaltar grietas finas |
| Contornos | Medir el área en píxeles |
| **Homografía** | Pasar de píxeles a metros cuadrados corrigiendo la perspectiva |
| Composición alfa | Pintar la máscara semitransparente sobre el video |

*Nota:* esta es la diapositiva que exige la sección 4 del documento técnico. Una imagen de
«antes y después» de la máscara sobre un hueco real.

---

## [9] Demostración

- **Video anotado:** un recorrido real de Montería con los daños marcados.
- **Mapa:** 48 puntos con su recorte, capa por tipo de daño.
- **En vivo:** `python scripts/presentar.py vivo` (video + GPX → detección → mapa, en un minuto).

*Nota:* dejar preparado el video y el mapa abiertos en pestañas aparte, por si la demo en
vivo falla. Ver el plan B en [presentacion.md](presentacion.md).

---

## [10] Resultados con datos reales

**Cinco recorridos, 48 daños revisados a mano uno por uno:**

| | Valor |
|---|---|
| Daños registrados | 48 |
| Revisados a mano | 48 (100 %) |
| Reales | 39 |
| Falsos positivos | 9 |
| **Precisión de campo** | **0,8125** |
| Velocidad (sin GPU) | 5,3–7,6 fotogramas/s |

Por clase: D00 3/3 reales · D10 0/2 · D20 32/39 · **D40 4/4 reales**.

*Nota:* el dato más contundente del proyecto. Ocho de cada diez avisos del sistema son
daños reales, comprobado a mano sobre video real.

---

## [11] Lo que todavía no está

Dicho sin adornos, porque también es resultado:

| Falta | Consecuencia | Por qué |
|---|---|---|
| Fotos propias etiquetadas | No hay ajuste fino: el modelo es el de RDD2022 | Etiquetar 300–500 imágenes es trabajo manual |
| Video de calibración | El área se reporta en píxeles, no en m² | Requiere un montaje fijo y un patrón de medida |
| Verdad de campo | No se midió la exhaustividad de campo | Requiere recorrer a pie y anotar a mano |

**Fuera del alcance, declarado:** medir la profundidad de un hueco (una sola cámara no
puede) y procesar en tiempo real dentro del vehículo.

*Nota:* esta diapositiva genera confianza. Un proyecto que sabe qué le falta se lee como
serio, no como incompleto.

---

## [12] Trabajo futuro

- Etiquetar los fotogramas propios y entrenar la **fase 2** del modelo.
- Calibrar la cámara para reportar **área en m²** y su error.
- Medir **longitud** de grietas (esqueletización de la máscara).
- **Profundidad** con cámara estéreo o sensor de profundidad del celular.
- Consulta del mapa por la Alcaldía y **priorización de reparaciones** por severidad.

---

## [13] Conclusiones

- Se construyó un sistema **funcional de punta a punta** con video y GPS reales.
- Precisión de campo medida y reportada: **0,8125** sobre 48 daños revisados a mano.
- El código, las pruebas (145 automáticas) y la documentación están en un repositorio
  público con integración continua.
- Los pendientes son **extensiones declaradas**, no fallos ocultos.

---

## [14] Cierre

- Repositorio: `github.com/vixanxva/TapaHuecos`
- Cómo se ejecuta:

```bash
pip install -e ".[web]"
tapahuecos-web          # interfaz en el navegador
tapahuecos procesar --video recorrido.mp4 --gpx recorrido.gpx
```

- Preguntas.

*Nota:* dejar esta diapositiva mientras se responde.
