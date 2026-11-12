# Guion para practicar la sustentación

Guion de **12 minutos** más **5 de preguntas**, con lo que se dice, lo que se muestra y los
tiempos. Las diapositivas están en [diapositivas.md](diapositivas.md) y los conceptos
explicados desde cero, en [conceptos.md](conceptos.md).

## 0. Antes de empezar (checklist)

**Media hora antes, en el equipo de la presentación:**

La demo completa sale de un solo comando, desde la carpeta del proyecto:

```bash
python scripts/presentar.py
```

Hace tres pasos y espera *Enter* entre uno y otro, para ir al ritmo del guion:

1. **Mapa** de la campaña (1:30): los 48 daños revisados, con su recorte al hacer clic.
2. **En vivo** (7:00): procesa `datos/demo/` (video + GPX) con la detección en pantalla,
   en un minuto aproximadamente, y abre el mapa que genera.
3. **Resultados** (8:30): la tabla de precisión de campo por clase (39 de 48: 0,8125).

Cada paso también corre por separado (`python scripts/presentar.py vivo`), y
`python scripts/presentar.py video` abre el video anotado de la campaña (plan B).

Necesita `salidas/campana_20261108/` (la carpeta `Prueba_region` de las salidas de Drive),
`datos/demo/` y `modelos/best_rdd.pt`. Si falta algo, el script lo dice antes de empezar.

**Comprobar:** correrlo completo una vez, que el mapa carga las calles (no cuadros grises)
y que la ventana de detección se ve en el proyector. Comprobarlo **con la red que se usará
ese día**, no antes en la casa.

**Plan B (no depender de la red):** capturas de pantalla del mapa y del video anotado en
una carpeta, el informe en PDF y el repositorio clonado en local. Si falla internet, la demo
en vivo se sustituye por las capturas y no se pierde nada del discurso.

**Reparto (si son varios):** una persona lleva las diapositivas 1–5 (problema, idea, flujo),
otra las 6–8 (datos, modelo, computación gráfica), otra las 9–14 (demo, resultados,
pendientes, cierre). Uno más maneja el computador: nadie más toca el teclado.

## 1. Cómo encuadrar lo que falta

El proyecto **está terminado en el alcance que declaró**: recibe video y GPS, detecta,
mide, ubica y entrega mapa y base de datos, y eso se demuestra con recorridos reales. Lo que
queda son **extensiones y validaciones que necesitan datos que todavía no tenemos**.
Frases concretas, aprendidas de memoria:

- «El sistema funciona de punta a punta con recorridos reales de Montería; lo que vamos a
  mostrar es el resultado de procesar cinco de ellos.»
- «El modelo que entregamos se entrenó con el dataset público RDD2022. Las fotos de
  Montería ya están grabadas, pero **etiquetarlas es trabajo manual**; por eso el ajuste
  fino queda como el siguiente paso, no como algo escondido.»
- «El área la reportamos en píxeles porque **falta el video de calibración**; con él sale en
  metros cuadrados y ya está el código para hacerlo.»
- «La precisión de campo la medimos revisando a mano los 48 daños. La exhaustividad todavía
  no, porque exige recorrer a pie y anotar cada hueco: es la parte que falta y lo decimos
  aquí.»
- «No medimos la profundidad de un hueco y no lo vamos a prometer: con **una sola cámara**
  no se puede. Está declarado como fuera del alcance.»

Regla de oro: **nunca digas que algo está hecho si no lo está**, pero tampoco lo pidas
perdón. Un proyecto que sabe exactamente qué le falta se lee como serio.

## 2. Guion minuto a minuto

### 0:00–0:45 · Portada y problema (diapositivas 1–2)

*En pantalla:* portada.

> «Buenos días. Somos [equipo] y presentamos TapaHuecos, un detector de daños en las vías.
> Las calles de Montería tienen huecos, grietas y piel de cocodrilo. Hoy se revisan a ojo,
> recorriéndolas a pie o en moto y anotando en papel. El problema no es solo reparar: es que
> **no existe un inventario con la ubicación y el tamaño de cada daño**. Sin eso, no hay
> forma de priorizar.»

*En pantalla:* foto de una calle con huecos.

### 0:45–1:30 · La idea (diapositiva 3)

> «Nuestra idea es simple: se recorre la calle **grabando video con el celular** y, al mismo
> tiempo, el recorrido GPS. Después, un programa revisa el video y entrega un mapa con cada
> daño. Una sola pasada en el vehículo reemplaza la inspección a pie, y el resultado es un
> inventario, no una impresión.»

*(Aquí se pulsa Enter en `scripts/presentar.py`: se abre el mapa de la campaña.)*

### 1:30–2:30 · Qué entrega (diapositiva 4)

> «De un video y su GPX salen cuatro cosas: el **video anotado**, un **recorte** de cada
> daño, una **base de datos** con tipo, tamaño y coordenada, y un **mapa interactivo**.
> Esto es el mapa de nuestra campaña: 48 puntos, y al hacer clic en uno se ve el recorte.»

*En pantalla:* el mapa real, clic en un punto mostrando el recorte.

### 2:30–3:45 · Las seis etapas (diapositiva 5)

> «Por dentro son seis etapas. **Entrada** lee el video, uno de cada dos fotogramas, para ir
> al doble de velocidad. **YOLO** encuentra los daños y les da un identificador de
> seguimiento. **OpenCV** recorta, realza y separa el daño del asfalto para medir su área.
> **GPS** toma la hora del fotograma y la busca en el recorrido, para saber dónde estaba.
> **Registro** guarda el recorte y una fila en la base de datos, **una sola vez por daño**.
> Y **salidas** arma el video anotado, el CSV y el mapa.»

*Señalar cada bloque del diagrama al nombrarlo.*

### 3:45–4:45 · Los datos (diapositiva 6)

> «Para entrenar usamos RDD2022: unas **47 000 imágenes** de vías de seis países, ya
> etiquetadas con las cuatro clases. Además grabamos **seis recorridos en Montería** con
> video y GPS. Cinco tienen su GPX sincronizado con el video.
> Y aquí quiero ser claro: **las fotos propias todavía no están etiquetadas.** Etiquetar
> entre 300 y 500 imágenes es trabajo manual; lo tenemos listo como insumo, pero el modelo
> que van a ver está entrenado con el dataset público.»

### 4:45–5:45 · El modelo (diapositiva 7)

> «Es un **YOLOv8s** entrenado en la GPU gratuita de Colab durante 85 épocas. En la prueba,
> el mAP de 0 a 1 queda en **0,633**, y por clase: las grietas y la piel de cocodrilo andan
> por 0,6 a 0,7, y el **hueco es el más flojo: 0,505**. Eso no es una sorpresa: los huecos
> de cerca, con hojas o agua, y las manchas claras del pavimento son los casos difíciles.
> Lo anotamos como el punto a mejorar.»

### 5:45–7:00 · Computación gráfica (diapositiva 8)

> «Esta es la parte de computación gráfica, y cada concepto está en un punto concreto del
> código. Pasamos a **escala de grises** para analizar sin color. Aplicamos **CLAHE** para
> realzar el contraste del asfalto. Un **filtro de convolución** quita el ruido de la
> textura. Con el **umbral de Otsu** separamos el daño del fondo. La **morfología** limpia la
> máscara y saca las grietas finas. Los **contornos** nos dan el área en píxeles.
> Y la **homografía** es la clave: un hueco lejano ocupa menos píxeles que uno cercano del
> mismo tamaño, así que proyectamos la imagen al plano de la vía para medir en metros
> cuadrados. Por último, la **composición alfa** pinta la máscara sobre el video.»

*En pantalla:* imagen de un hueco, luego la misma con la máscara superpuesta.

### 7:00–8:30 · Demostración (diapositiva 9)

*Opción A (en vivo, paso 2 de `scripts/presentar.py`):*

> «Vamos a correr el sistema completo frente a ustedes: entra un video y su GPS, y salen
> los recortes, la base de datos y el mapa. Este video de prueba está armado con imágenes
> de RDD2022 y un recorrido simulado por la Avenida Primera.»

*Pulsar Enter: se abre la ventana con la detección y, al minuto, el mapa del resultado.
**No esperar en silencio**: mientras corre, explicar qué significa cada recuadro.*

*Opción B (video anotado, siempre):*

> «Este es el video anotado de uno de los recorridos reales: cada daño aparece con su clase,
> su identificador y su área.»

*Reproducir 15 segundos del video anotado y volver al mapa.*

### 8:30–9:45 · Resultados (diapositiva 10)

> «Y ahora el dato que más nos importa, porque no viene del laboratorio sino de la calle.
> Procesamos cinco recorridos y **revisamos a mano los 48 daños registrados**, uno por uno,
> mirando el recorte de cada uno. **39 eran daños reales y 9 falsos positivos: precisión de
> campo 0,8125.** Es decir, ocho de cada diez avisos del sistema corresponden a un daño de
> verdad. En los huecos la precisión fue perfecta: los cuatro huecos detectados eran reales.
> En velocidad, en un portátil sin tarjeta gráfica, va a entre 5 y 7 fotogramas por segundo.»

### 9:45–10:45 · Lo que falta (diapositiva 11)

> «Ahora lo que nos falta, y lo decimos sin adornos. Primero: **no hemos etiquetado las
> fotos de Montería**, así que el modelo es el de RDD2022 y no tiene ajuste fino; eso lo
> resuelve el etiquetado, que es trabajo manual. Segundo: **falta el video de calibración**,
> por eso el área sale en píxeles y no en metros cuadrados; el código ya está listo. Y
> tercero: **no medimos la exhaustividad**, es decir, cuántos daños reales se nos escapan,
> porque para eso hay que recorrer la calle a pie y anotar cada hueco.
> Y hay dos cosas que quedan **fuera del alcance** y no prometemos: medir la **profundidad**
> del hueco, porque con una sola cámara no se puede, y el **tiempo real** dentro del
> vehículo.»

### 10:45–11:30 · Futuro y conclusiones (diapositivas 12–13)

> «Como trabajo futuro: etiquetar y entrenar la fase 2, calibrar para dar área en metros
> cuadrados, medir la longitud de las grietas, y la profundidad con un sensor del celular.
> Para cerrar: construimos un sistema que **funciona de punta a punta con video y GPS
> reales**, medimos su precisión en la calle y la reportamos, y el código, las 145 pruebas y
> la documentación están en un repositorio público. Los pendientes están declarados: no son
> fallos ocultos, son el siguiente paso.»

### 11:30–12:00 · Cierre (diapositiva 14)

> «El repositorio es público y se ejecuta con dos comandos. Gracias. Con gusto respondemos
> sus preguntas.»

## 3. Preguntas probables y respuestas cortas

| Pregunta | Respuesta (30 s) |
|---|---|
| ¿Por qué no miden la profundidad del hueco? | Con una sola cámara no hay forma de saber cuántos centímetros baja: falta información de paralaje. Se necesitaría estéreo, un sensor de profundidad o LiDAR. Está declarado como fuera del alcance y como trabajo futuro. |
| ¿Por qué no es en tiempo real? | El diseño procesa el video después del recorrido. El modo cámara existe y funciona, pero en un portátil sin GPU va a 5–7 fotogramas por segundo; para tiempo real habría que exportar el modelo a ONNX y usar un equipo con GPU. |
| ¿Qué tan preciso es el área? | Hoy el área se reporta en píxeles. Con la homografía sale en metros cuadrados, pero **falta el video de calibración** para validarla. No vamos a dar un número de error que no hemos medido. |
| ¿Y si el GPS falla? | El sistema **no inventa** coordenadas: si la hora del daño cae fuera del recorrido GPS o hay un hueco de más de 30 segundos, guarda el daño sin coordenada y avisa. |
| ¿Cuántos daños se les escapan? | No lo hemos medido: es la exhaustividad de campo y requiere recorrer a pie y anotar cada hueco. Lo que sí medimos es la precisión: 0,8125. |
| ¿Por qué D40 es el peor? | Los huecos cambian mucho de aspecto: de cerca con hojas, agua o tierra se ven distinto, y las manchas claras del pavimento se parecen a un hueco. Se arregla con más ejemplos etiquetados, no con parámetros. |
| ¿Funciona con videos de otro celular? | Sí, si el video es `.mp4` y el nombre trae la hora (`VID_AAAAMMDD_HHMMSS`). Si no, se indica la hora con una opción. La rotación del celular se corrige sola con los metadatos del video. |
| ¿Se puede usar sin internet? | Sí, el procesamiento es local. Solo el mapa necesita internet para mostrar las calles. |
| ¿Cuánto tarda un recorrido? | Depende del largo y del equipo. En un portátil sin GPU, unos 2,5 minutos por cada 35 segundos de video. Con GPU es mucho más rápido. |

## 4. Plan B

| Si falla… | Se hace… |
|---|---|
| Internet | Se usan las capturas del mapa y el video anotado ya descargado. Se dice: «el mapa necesita conexión para mostrar las calles; estas son las capturas de la corrida». |
| La demo en vivo se queda colgada | Se pasa al video anotado sin comentar el fallo («mientras termina, veamos el resultado de la corrida anterior»). |
| Se acaba el tiempo | Se saltan las diapositivas 12 y 13 y se va directo al cierre. Nunca se salta la 10 (resultados) ni la 11 (lo que falta). |
| El proyector cambia los colores | No se afirma nada sobre el color de la máscara; se habla de la forma. |

## 5. Ensayo

- **Un ensayo completo cronometrado**, mínimo. Objetivo: terminar entre 11 y 12 minutos.
- Practicar el cambio de diapositiva **diciendo la frase anterior**, sin silencios.
- Practicar la respuesta a las tres preguntas más incómodas (profundidad, área, exhaustividad).
- Practicar el paso de «lo que falta» sin bajar el tono ni acelerar: es la parte que genera
  confianza.
