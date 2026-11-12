# Conceptos clave de TapaHuecos, explicados desde cero

Este documento está dirigido a quien llega al proyecto TapaHuecos **sin saber nada de
informática, de visión por computador ni de GPS**. Se lee de corrido: empieza por lo más
elemental (qué es una foto, qué es un video, qué es un mapa) y termina en los detalles propios
del proyecto (cómo se mide un hueco, cómo se guardan los resultados, qué falta por hacer). Cada
concepto trae una analogía cotidiana y una frase que dice **dónde aparece**. Al final hay un
glosario alfabético de consulta rápida.

## 1. Qué es TapaHuecos y qué entrega

Imaginen que recorren una ciudad en carro con el teléfono grabando video desde el parabrisas. Al
volver a casa tienen un video larguísimo donde, de vez en cuando, aparece un hueco, una grieta o
una zona con piel de cocodrilo. TapaHuecos es una **herramienta de consola escrita en Python**
que recibe ese video **y** el recorrido GPS grabado al mismo tiempo (un archivo llamado GPX), lo
mira fotograma por fotograma y devuelve cuatro cosas: **(1)** el mismo video anotado con los
daños marcados, **(2)** una carpeta con el recorte de cada daño, **(3)** una base de datos
SQLite con el tipo, el tamaño aproximado y la coordenada de cada daño, y **(4)** un mapa HTML
interactivo. Piénsenlo como un inspector incansable que revisa el video y anota cada daño con su
coordenada.

## 2. La imagen digital: píxeles, resolución y color

Una imagen digital no es más que una **cuadrícula de cuadritos diminutos**; cada uno se llama
**píxel** (*picture element*). Es igual que un mosaico de cerámica: de cerca son cuadritos
sueltos, de lejos forman la figura. Cuando decimos que una foto tiene **1920 x 1080 píxeles**
hablamos de **resolución**: 1920 columnas y 1080 filas. Cada píxel guarda un color descrito con
**tres números**, uno por canal: **rojo, verde y azul** (RGB en inglés), aunque OpenCV los lee
en orden **BGR** por razones históricas. Cuando solo importa la luminosidad, la imagen pasa a
**escala de grises**, con una cifra por píxel: es una fotocopia en blanco y negro.

**Dónde aparece:** TapaHuecos trabaja con videos de 1080 x 1920 píxeles y varios pasos de su
análisis empiezan pasando el recorte del daño a escala de grises.

## 3. El video: muchísimas fotos seguidas

Un video es **una sucesión rapidísima de fotos fijas** llamadas **fotogramas** (*frames*). Si se
muestran 30 por segundo, el cerebro las une y ve movimiento; esa velocidad se mide en **fps**
(*frames per second*). Hay celulares que graban con una frecuencia que sube y baja según la luz
o el movimiento: eso es la **tasa de fotogramas variable**. El detalle importante es que un
video **no lleva la hora escrita en cada fotograma**, solo una hora de inicio y una frecuencia
media; si la frecuencia real no coincide, los tiempos se desfasan y ese desfase se convierte en
metros de error en el mapa.

**Dónde aparece:** TapaHuecos no procesa todos los fotogramas, sino **1 de cada N** (el valor
está en `config.yaml`), porque un daño permanece en pantalla varios fotogramas seguidos.

## 4. Inteligencia artificial, aprendizaje automático y redes neuronales

La "inteligencia artificial" de la que se habla aquí es, en concreto, **aprendizaje
automático**. En la programación clásica una persona escribe las reglas ("si el píxel es rojo,
haz esto"); aquí **se le muestran al programa miles de ejemplos ya resueltos y él deduce la
regla por su cuenta**. La analogía de la cocina sirve: nadie puede escribir la receta exacta del
guiso que está salado, pero quien prueba diez mil guisos con la etiqueta "salado / no salado"
acaba desarrollando olfato. La pieza que aprende es una **red neuronal**: no es un cerebro, sino
una **cadena de operaciones matemáticas en capas** con miles o millones de "perillas"
(parámetros) que al principio están al azar. **Entrenar** es ajustar esas perillas hasta que la
respuesta coincida con la etiqueta correcta.

**Dónde aparece:** TapaHuecos usa una red neuronal llamada **YOLOv8**, entrenada en Google Colab
con una tarjeta gráfica (GPU T4) durante 85 vueltas completas sobre el dataset RDD2022.

## 5. Clasificar, detectar y segmentar: tres tareas distintas

**Clasificar** una imagen es responder "¿qué es esto?" con una sola respuesta para toda la foto,
como ponerle un nombre. **Detectar objetos** es responder "¿qué hay y dónde?" y devolver una
zona por cada cosa encontrada: es señalar con el dedo cada daño dentro del video. **Segmentar**
es responder "¿exactamente qué píxeles son esto?", dibujando el contorno fino: recortar con
tijeras en vez de poner un rectángulo alrededor.

**Dónde aparece:** las tres tareas se reparten entre etapas: YOLO **detecta** (etapa 2) y OpenCV
**segmenta y recorta** el daño dentro del recuadro detectado (etapa 3).

## 6. La caja envolvente, el nivel de confianza y el IoU

La forma práctica de decir "está aquí" es dibujar un **rectángulo** alrededor del hallazgo: la
**caja envolvente** o *bounding box*. Es como pegarle una etiqueta rectangular a un objeto
dentro de una foto: no es perfecta, pero es rápida y suficiente. Junto a la caja viene un
**nivel de confianza**, un número entre 0 y 1 que dice qué tan seguro está el sistema: es la
seguridad de un testigo, donde 0,95 es "lo vi clarísimo" y 0,32 es "podría ser una sombra"; por
debajo del **umbral** que fija el usuario, la detección se descarta. Cuando dos cajas pretenden
describir el mismo objeto se mide cuánto se solapan con el **IoU** (*Intersection over Union*):
el área común dividida entre el área total que ocupan juntas. Si es 1 son la misma caja; si es
0, no se tocan.

**Dónde aparece:** cada daño de TapaHuecos nace con una caja, una clase y una confianza, y esos
tres datos viajan por todo el flujo hasta la base de datos.

## 7. YOLO: por qué es rápido, y qué significan la n y la s

**YOLO** viene de *You Only Look Once*, "solo miras una vez". Su idea fue dejar de analizar la
imagen por partes y hacer **una sola pasada** que devuelve todas las cajas y todas las clases a
la vez: la diferencia entre un portero que revisa a cada persona una por una y otro que ve la
fila completa de un vistazo. Por eso es la familia de detectores más usada en tiempo real, y
cada versión viene en **tamaños** nombrados con letras: **n** de *nano* (el más veloz y el menos
preciso) y **s** de *small*, un paso más grande, con mejor puntería y todavía ligero.

**Dónde aparece:** el proyecto usa **YOLOv8s**. La inferencia tarda unos **9,7 milisegundos por
imagen** en la GPU de Colab; en un portátil sin GPU, unos **5,3 a 7,6 fotogramas por segundo**.

## 8. El dataset: etiquetas, ejemplos positivos y negativos, particiones

Para que una red neuronal aprenda hace falta un **dataset**: una colección grande de imágenes
con su **etiqueta** (*label*), la respuesta correcta escrita al lado. Armarlo se parece a
preparar un examen: alguien tiene que marcar cada respuesta a mano. Hay dos tipos de ejemplo, y
los dos importan: **positivos**, donde el daño sí está, y **negativos**, donde no hay daño
(pavimento limpio, sombras, manchas de aceite) y hay que aprender a distinguirlo; sin negativos
el modelo se vuelve paranoico. El dataset se parte en tres, y la analogía es la del estudiante:
**entrenamiento** son los ejercicios de práctica, **validación** son los simulacros intermedios
y **prueba** es el examen final, que se guarda bajo llave y solo se usa una vez al final.

**Dónde aparece:** RDD2022 es el dataset base, y a él se sumarán los **seis videos propios
grabados en Montería** (Córdoba, Colombia) con sus recorridos GPS.

## 9. El sobreajuste: memorizar en vez de aprender

Si un estudiante repite el libro de memoria saca diez en los ejercicios de casa y cero en el
examen. Eso es el **sobreajuste**: el modelo se aprendió los ejemplos exactos que vio, no la
regla general, y fallará con cualquier imagen nueva. La defensa es triple: no dejar que vea
nunca el conjunto de prueba, vigilar con la **validación** durante el entrenamiento y añadir
**ejemplos negativos** y variaciones de brillo y encuadre.

**Dónde aparece:** por eso las métricas del proyecto salen siempre del conjunto de prueba, nunca
del de entrenamiento.

## 10. RDD2022 y las cuatro clases de daño

**RDD2022** (*Road Damage Dataset 2022*) es un dataset **público** de unas **47 000 imágenes**
de vías de **Japón, India, República Checa, Noruega, Estados Unidos y China**, anotadas a mano
en un formato de texto estándar llamado **Pascal VOC**. Sirve de base porque etiquetar 47 000
imágenes cuesta muchísimo tiempo y ya está hecho. TapaHuecos maneja exactamente **las cuatro
clases de RDD2022**: **D00**, grieta **longitudinal** (una raya larga en el mismo sentido de la
vía); **D10**, grieta **transversal** (cruza la vía de lado a lado, como una junta); **D20**,
**piel de cocodrilo** (una malla de grietas entrecruzadas, como un vitral roto); y **D40**, el
**hueco** o bache, el agujero que se siente al pasar con el carro.

**Dónde aparece:** el proyecto descargó y verificó **cinco países** (Japón, India, República
Checa, Estados Unidos y China-Moto) y tiene un script para pasarlos al formato de YOLO.

## 11. Entrenamiento, épocas y ajuste fino: las dos fases del modelo

El entrenamiento se hace por **épocas**: una época es una pasada completa por todas las imágenes
de entrenamiento, y más pasadas son más oportunidades de aprender, hasta que empieza a
memorizar. Existe un truco fundamental para no empezar de cero: el **ajuste fino**
(*fine-tuning*), que toma un modelo **ya entrenado** con muchísimas imágenes y lo repasa con las
propias, que son pocas; las primeras capas ya saben cosas universales (bordes, contrastes,
formas) y solo se retocan las últimas. Es como contratar a un cocinero experimentado: no hay que
enseñarle a sostener el cuchillo, solo la sazón de la casa.

**Dónde aparece:** el proyecto prevé **dos fases**. La **fase 1**, entrenar con RDD2022, ya está
hecha y dio `best_rdd.pt`. La **fase 2** sería el ajuste fino con fotos propias de Montería
etiquetadas y daría `best.pt`; **todavía no está hecha** porque aún no hay fotos propias
etiquetadas, así que hoy el sistema usa el modelo de RDD2022.

## 12. Las métricas, contadas como un examen médico

Imaginen una prueba para detectar una enfermedad. Hay cuatro resultados posibles, y son la base
de todo: **verdadero positivo** (enfermo y el test lo dice), **verdadero negativo** (sano y el
test lo dice), **falso positivo** (sano y el test grita "enfermo": una falsa alarma) y **falso
negativo** (enfermo y el test no lo ve: el error silencioso, el más peligroso). La tabla de esas
cuatro casillas es la **matriz de confusión**. De ahí salen dos medidas que hay que mirar
juntas: la **precisión** responde "de todo lo que marqué como daño, ¿cuánto era daño de verdad?"
y la **exhaustividad** (en inglés *recall*) responde "de todos los daños que había, ¿cuántos
alcancé a encontrar?". La comparación con la **red de pesca** lo aclara: una red de agujeros muy
finos atrapa todos los peces pero también arrastra latas (alta exhaustividad, baja precisión);
una de agujeros grandes solo trae peces limpios pero deja escapar muchos. Como no se puede
optimizar una sin castigar la otra, existe el **F1**, un número que combina las dos. Y para
exigir además que la caja esté en el sitio correcto se usa el **IoU** como nota de corte: de ahí
nace el **mAP**, que resume el desempeño sobre todas las clases. `mAP@0.5` exige un solapamiento
del 50 %; `mAP@0.5:0.95` es mucho más estricto y por eso da más bajo.

Los números reales del proyecto en el conjunto de prueba son:

| Clase | Precisión | mAP@0.5 |
|---|---|---|
| D00 grieta longitudinal | 0,664 | 0,706 |
| D10 grieta transversal | 0,634 | 0,613 |
| D20 piel de cocodrilo | 0,692 | 0,708 |
| D40 hueco | 0,624 | 0,505 |

En total: **mAP@0.5 = 0,633**, **mAP@0.5:0.95 = 0,329** y **exhaustividad total 0,584**. La
clase más débil es **D40 (huecos)**, con exhaustividad **0,445**: se le escapa más de la mitad
de los huecos. Un **falso positivo concreto** del proyecto: una **mancha clara de pavimento**
marcada como hueco, que en realidad es pavimento descolorido.

## 13. El procesamiento de imágenes con OpenCV

**OpenCV** es la caja de herramientas de la fontanería de la imagen: corta, filtra, cambia
colores y mide. Sus herramientas, una a una: **escala de grises**, para quedarse solo con la
luminosidad; **filtro de convolución**, que pasa una ventana pequeña (por ejemplo de 3x3) por
toda la imagen y reemplaza cada píxel por una mezcla ponderada de sus vecinos; **desenfoque
gaussiano**, que promedia cada píxel con sus vecinos, como mirar por un vidrio esmerilado;
**CLAHE** (ecualización adaptativa del contraste), que estira el contraste **por zonas
separadas** en lugar de aplicarlo a toda la foto por igual, es decir, ilumina **por barrios**
para realzar las grietas oscuras sin quemar las zonas ya claras; **umbralización de Otsu**, que
convierte la imagen en blanco y negro **eligiendo sola el punto de corte** según el histograma,
como encontrar la frontera entre lo claro y lo oscuro; **morfología**, que limpia la forma de
las manchas como quien trabaja con plastilina: la **apertura** borra puntitos sueltos, el
**cierre** rellena huecos pequeños y el **black-hat** resalta lo más oscuro que su alrededor,
que es justo la silueta de una grieta; y por último los **contornos**, las fronteras que se
repasan con lápiz alrededor de cada mancha y que permiten medir el **área en píxeles**.

**Dónde aparece:** es exactamente la etapa 3 del flujo: recortar la caja, realzar el contraste,
obtener la máscara, trazar el contorno y medir el área.

## 14. Perspectiva y homografía: medir en metros cuadrados

En una foto de la vía **un hueco del mismo tamaño real ocupa muchos píxeles si está cerca y muy
pocos si está lejos**: es la perspectiva del carro que parece grande de cerca y enano de lejos.
Por eso el área en píxeles no es una medida justa: dos huecos de un metro cuadrado pueden dar
500 y 80 píxeles según la distancia. La solución es una **transformación proyectiva** u
**homografía**, que "endereza" la imagen hasta ver la carretera **como si la miráramos desde
arriba**, desde un dron imaginario en picada vertical; en ese plano los píxeles sí corresponden
a metros reales. Para calcularla hace falta **calibrar**: grabar una marca de tamaño conocido
—un papel, una cinta— a distintas distancias, para saber cuántos píxeles equivalen a un metro.

**Dónde aparece (estado real):** el proyecto **todavía no tiene la calibración hecha**, así que
hoy **el área se reporta solo en píxeles**. Falta el video de calibración y, con él, el archivo
que guarda la transformación.

## 15. GPS, GPX y por qué la hora lo une todo

El **GPS** funciona con satélites que orbitan la Tierra y transmiten señales de radio con su
posición y su hora; el receptor calcula cuánto tardó cada señal y, por triangulación, deduce
dónde está. La posición se expresa con **latitud** (norte-sur) y **longitud** (este-oeste), y la
**precisión en metros** dice cuánto se puede confiar en ella: a cielo abierto son unos pocos
metros, y entre edificios altos la señal rebota en las fachadas y el error crece. El **GPX** es
un **archivo de texto** con el recorrido: una lista ordenada de puntos, cada uno con su latitud,
su longitud y **su hora**.

Ahora el punto más frágil del sistema: el video **no guarda la posición** y el GPX **no guarda
las imágenes**; lo único que ambos comparten es **el tiempo**. TapaHuecos mira la hora del
fotograma del daño, busca ese instante en el GPX y de ahí saca la coordenada. Dos advertencias:
el GPS reporta en **hora UTC**, el tiempo universal sin husos ni horario de verano, mientras el
teléfono suele grabar **hora local** (en Colombia, UTC−5), y un signo equivocado manda el daño a
otro continente; y si el **reloj de la cámara va adelantado** respecto al del GPS, todos los
daños se corren a lo largo del recorrido. Como además el GPX guarda un punto cada cierto tiempo,
el programa calcula **por interpolación** dónde estaba el vehículo en el instante exacto del
fotograma, repartiendo la distancia entre los dos puntos que lo rodean.

**Dónde aparece:** la etapa 4 hace esa traducción; si un fotograma cae fuera del tramo cubierto
por el GPX, la herramienta avisa y deja ese daño sin coordenada en vez de inventarse una. Cinco
de los recorridos de la campaña tienen su GPX cubriendo el video de principio a fin.

## 16. Seguimiento de objetos: no contar el mismo hueco veinte veces

Un hueco aparece en decenas de fotogramas seguidos, cada vez más grande conforme el carro se
acerca, y luego se pierde por el retrovisor. Si se anotara uno por fotograma, un solo hueco
llenaría la lista con veinte filas. Para evitarlo existe el **seguimiento de objetos**
(*tracking*), que asigna a cada objeto un **ID de seguimiento** que se mantiene mientras el
objeto siga apareciendo: el sistema compara la caja nueva con las que ya tenía y decide si es
"el mismo daño, ID 17". **ByteTrack** es un algoritmo de seguimiento muy eficiente: su idea es
**aprovechar también las detecciones de baja confianza**, no para inventar daños nuevos sino
para no perder el rastro de uno ya conocido; es como reconocer a alguien de espaldas, señal
débil pero suficiente.

**Dónde aparece:** la etapa 2 combina YOLO con ByteTrack, y la etapa 5 aprovecha ese ID para
guardar **una sola foto y una sola fila por daño**.

## 17. Guardar los resultados: SQLite y CSV

Una **base de datos SQLite** es un **archivo único** que contiene **tablas**; cada tabla tiene
**columnas** (tipo de daño, área, latitud, longitud, confianza) y **filas** (un registro por
daño). Es como una hoja de cálculo con reglas, que responde preguntas del tipo "dame todos los
huecos de más de un metro cuadrado" y que ya viene incluida en Python. Un **CSV** (*valores
separados por comas*) es un **archivo de texto plano** donde cada fila es un registro: no tiene
reglas ni índices, pero se abre con cualquier programa y se puede enviar por correo. En resumen:
**SQLite es para trabajar; CSV, para compartir**.

**Dónde aparece:** la etapa 5 escribe una fila en SQLite por daño y guarda el recorte `.jpg`;
las salidas incluyen `danos.db`, `danos.csv` y la carpeta de recortes.

## 18. El mapa interactivo: Leaflet, capas y mosaicos

Un **mapa interactivo** se arrastra, se acerca y sus puntos se pueden tocar. La librería web más
usada para esto es **Leaflet**, que se encarga del zoom, el arrastre y los marcadores. Una
**capa** es cada nivel de contenido dibujado encima del mapa: la capa de puntos y la del
recorrido se pueden encender o apagar por separado. Detalle clave: Leaflet **no fabrica los
mapas**, no conoce la geografía; se apoya en un **proveedor de mosaicos** (los *tiles*), que
parte el mundo en **cuadritos** de 256 x 256 píxeles y los entrega según el nivel de zoom, como
un álbum de fichas. Existe un problema frecuente: los proveedores **pueden bloquear las
descargas** cuando ven demasiadas peticiones automatizadas o un uso fuera de sus condiciones, y
el navegador recibe un **403**, "no autorizado", que en pantalla se ve como cuadritos vacíos o
grises.

**Dónde aparece:** la cuarta salida de TapaHuecos es `mapa.html`, que se abre en el navegador y
muestra cada daño como un marcador sobre su coordenada.

## 19. El taller del software: repositorio, Git, GitHub y pruebas automáticas

El **repositorio** es el conjunto de todos los archivos del proyecto más su historial; **Git**
lleva ese historial guardando **instantáneas** en lugar de sobrescribir. Cada instantánea es un
**commit**, con un mensaje que explica el cambio; una **rama** (*branch*) es una línea paralela
de trabajo, como cocinar una porción aparte para probar el sazón antes de echarle sal a la olla
completa. **GitHub** aloja el repositorio en internet para trabajar en equipo: allí un **issue**
es una ficha de tarea o de problema con su número ("arreglar el desfase de hora #34") y un
**Pull Request** es una propuesta de cambio que otra persona revisa antes de aceptarla, como la
mesa de revisión del taller. La **integración continua** descarga el proyecto y ejecuta sus
**pruebas automáticas** en cada propuesta: pequeños programas que verifican que cada pieza siga
funcionando, el control de calidad que delata en segundos cualquier rotura.

**Dónde aparece:** TapaHuecos vive en Git y GitHub con sus issues y su integración continua, y
su suite tiene **145 pruebas automáticas**.

## 20. Métrica del modelo y métrica de campo: parecidas, no iguales

Las **métricas del modelo** (mAP, precisión, exhaustividad) se calculan sobre **un conjunto fijo
de imágenes de prueba**: son una nota de examen, justa y repetible, ideal para comparar
versiones del modelo, pero el examen es un recorte de la realidad. La **métrica de campo** se
calcula sobre **recorridos reales completos**, revisando a mano las detecciones: es más lenta,
pero es la nota que le importa a quien usará la herramienta.

**Dónde aparece:** el proyecto sí tiene métrica de campo. Cinco recorridos procesados y
revisados a mano dan **48 daños revisados, 39 reales y 9 falsos positivos**, es decir, una
**precisión de campo de 0,8125**. En cambio **no hay exhaustividad de campo** ni **error de
posición** medidos, porque para eso haría falta una **verdad de campo** levantada a pie,
anotando qué daños existen realmente en el recorrido.

## 21. Los límites físicos: por qué una cámara no mide profundidad

Con una sola cámara y una sola foto **no se puede saber la profundidad de un hueco**: es
geometría, no falta de programación. Al proyectar el mundo tridimensional sobre un plano
bidimensional se pierde una dimensión, la profundidad: en una foto, una torre lejana y un
juguete pequeño pueden ocupar lo mismo, y nada dice cuál es cuál. Por eso TapaHuecos mide el
**área** (ancho y largo, visibles en el plano de la vía), pero **no la profundidad**, para lo
cual harían falta dos cámaras (estereoscopía) o un sensor de proximidad. El segundo límite es de
velocidad: **no se procesa el video en vivo dentro del carro**, sino después, y en un portátil
sin GPU el ritmo medido es de **5,3 a 7,6 fotogramas por segundo**.

## 22. El flujo completo, en seis etapas

**(1) Entrada**, leer el video y tomar 1 de cada N fotogramas; **(2) YOLO**, detectar cada daño
y seguirle la pista con su ID; **(3) OpenCV**, recortar, realzar el contraste, sacar la máscara,
trazar el contorno y medir el área en píxeles y, si hay calibración, en metros cuadrados; **(4)
GPS**, convertir la hora del fotograma en una posición interpolada del GPX; **(5) Registro**,
guardar el recorte `.jpg` y **una fila en SQLite, una sola vez por daño**; y **(6) Salidas**,
generar el video anotado, los recortes, `danos.db`, `danos.csv` y `mapa.html`.

## 23. Dónde está el proyecto hoy, sin adornos

- El sistema **funciona de principio a fin** con recorridos reales de Montería.
- Cinco recorridos están procesados y revisados a mano: **48 daños revisados, 39 reales y 9
falsos positivos**, con **precisión de campo 0,8125**.
- **Todavía no hay fotos propias de Montería etiquetadas**, así que la **fase 2** (el ajuste
fino, `best.pt`) **no está hecha**: el modelo actual es el de RDD2022.
- **Sin calibración de cámara**, el área se reporta **solo en píxeles**; falta el video de
calibración para el área en metros cuadrados.
- **No hay verdad de campo** levantada a pie, así que no se ha medido la **exhaustividad de
campo** ni el **error de posición**.
- La velocidad medida en un portátil sin GPU es de unos **5,3 a 7,6 fotogramas por segundo**.
- **No mide profundidad del hueco** (una cámara no puede) ni **procesa en tiempo real**.

La tubería está terminada; lo que falta son **datos propios etiquetados**, **calibración** y
**mediciones de campo**, tareas que piden trabajo humano más que más programación.

## Glosario

- **Ajuste fino (*fine-tuning*)**: repasar un modelo ya entrenado con imágenes propias en vez de empezar de cero.
- **Área en píxeles**: número de píxeles que encierra el contorno de un daño; no es una medida física.
- **Bounding box (caja envolvente)**: rectángulo que rodea cada objeto detectado.
- **ByteTrack**: seguidor que aprovecha también las detecciones de baja confianza para no perder un rastro.
- **Calibración**: grabar una marca de tamaño conocido para saber cuántos píxeles equivalen a un metro.
- **CLAHE**: realce del contraste aplicado por zonas, para no quemar las partes ya claras.
- **Clasificación**: decir qué es una imagen, sin señalar dónde.
- **Commit**: instantánea del proyecto en Git con un mensaje que explica el cambio.
- **Confianza**: número entre 0 y 1 que expresa la seguridad del detector en un hallazgo.
- **Convolución**: operación que recorre la imagen con una ventana y mezcla cada píxel con sus vecinos.
- **Contorno**: frontera trazada alrededor de una mancha; permite medir su área.
- **CSV**: archivo de texto plano con los datos separados por comas, cómodo para compartir.
- **Dataset**: colección de ejemplos ya resueltos (imágenes con su etiqueta) para entrenar o evaluar.
- **Desenfoque gaussiano**: suavizado que promedia cada píxel con sus vecinos y borra el ruido fino.
- **Detección de objetos**: encontrar qué hay en la imagen y dónde, señalando cada objeto por separado.
- **Entrenamiento**: proceso de ajustar los parámetros de una red neuronal viendo ejemplos.
- **Escala de grises**: imagen con un solo valor de luminosidad por píxel.
- **Exhaustividad (*recall*)**: de todos los daños que existían, cuántos encontró el sistema.
- **F1**: número que combina precisión y exhaustividad y castiga los extremos.
- **Falso negativo**: daño real que el sistema no marcó; el error silencioso.
- **Falso positivo**: algo que no es un daño y el sistema marcó como daño; una falsa alarma.
- **Fotograma (*frame*)**: cada foto fija que, vista muy rápido, forma un video.
- **FPS**: fotogramas por segundo, la velocidad de grabación o reproducción.
- **Git**: programa que guarda el historial de un proyecto con instantáneas.
- **GitHub**: sitio donde se aloja un repositorio Git para trabajar en equipo.
- **GPX**: archivo de texto con el recorrido GPS: puntos con latitud, longitud y hora.
- **GPU**: tarjeta gráfica; acelera el entrenamiento y la inferencia de redes neuronales.
- **Homografía**: transformación que endereza la imagen para ver el plano de la vía desde arriba.
- **ID de seguimiento**: número de identidad que se mantiene sobre un mismo objeto mientras dura su rastro.
- **Integración continua**: servicio que ejecuta las pruebas automáticas en cada cambio propuesto.
- **Interpolación**: calcular la posición en un instante que cae entre dos puntos conocidos.
- **IoU**: medida de cuánto se solapan dos cajas respecto al área que ocupan juntas.
- **Issue**: ficha de tarea o de problema en GitHub, con su número.
- **Latitud y longitud**: coordenadas de una posición sobre la Tierra (norte-sur y este-oeste).
- **Leaflet**: librería web para mapas interactivos.
- **mAP**: precisión media promedio; resume el desempeño del detector sobre todas las clases.
- **Matriz de confusión**: tabla de cuatro casillas con aciertos, falsas alarmas y errores silenciosos.
- **Morfología**: operaciones que limpian la forma de las regiones (apertura, cierre, black-hat).
- **OpenCV**: librería para leer, recortar, filtrar y medir imágenes y video.
- **Otsu**: forma automática de elegir el corte entre claro y oscuro al pasar a blanco y negro.
- **Pascal VOC**: formato de texto estándar para anotar datasets de detección.
- **Píxel**: cada cuadrito diminuto de una imagen digital; su unidad mínima.
- **Precisión**: de todo lo que el sistema marcó como daño, cuánto era daño de verdad.
- **Precisión del GPS**: margen de error esperado de una posición; nunca es cero.
- **Prueba automática (*test*)**: programa que verifica que una pieza siga funcionando; en TapaHuecos hay 145.
- **Pull Request**: propuesta de cambio que otra persona revisa antes de unirla a la rama principal.
- **Rama (*branch*)**: línea paralela de trabajo en Git.
- **RDD2022**: dataset público de unas 47 000 imágenes anotadas de daños en vías de seis países.
- **Red neuronal**: cadena de operaciones matemáticas en capas cuyos parámetros se ajustan al entrenar.
- **Repositorio**: el conjunto de todos los archivos del proyecto más su historial.
- **Resolución**: número de columnas y filas de píxeles de una imagen.
- **RGB y BGR**: los tres canales de color (rojo, verde, azul); BGR es el orden que usa OpenCV.
- **Segmentación**: decir exactamente qué píxeles pertenecen al objeto.
- **Sobreajuste**: cuando el modelo memoriza los ejemplos vistos en vez de aprender la regla.
- **SQLite**: base de datos en un solo archivo, con tablas y filas, incluida en Python.
- **Tasa de fotogramas variable**: frecuencia de grabación que sube y baja en lugar de ser constante.
- **Tracking (seguimiento de objetos)**: mantener la identidad de un mismo objeto a lo largo de los fotogramas.
- **Umbral**: valor de corte a partir del cual se acepta o se descarta una detección.
- **UTC**: hora universal de referencia, sin husos ni horario de verano; la que reporta el GPS.
- **Validación**: parte del dataset usada durante el entrenamiento para detectar la memorización.
- **Verdad de campo**: recorrido a pie anotando qué daños existen, para medir cuántos se escaparon.
- **YOLO**: familia de detectores que analiza la imagen en una sola pasada, lo que la hace muy rápida.
