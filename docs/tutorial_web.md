# Tutorial de la interfaz web

Interfaz local para ejecutar el proyecto desde el navegador sin escribir comandos. Por
dentro lanza los mismos comandos de consola y muestra su salida en vivo.

## 1. Arrancar

```bash
pip install -e ".[web]"
tapahuecos-web                 # o: python -m tapahuecos.web
```

Abrir <http://127.0.0.1:5000>. Debe ejecutarse desde la carpeta del proyecto (donde está
`config.yaml`). `--puerto 5001` cambia el puerto y `--host` la interfaz de red.

## 2. Cómo se lee un formulario (regla de oro)

Cada formulario mezcla dos cosas distintas y conviene no confundirlas:

| En pantalla | ¿Se envía al comando? |
|---|---|
| Un campo **con texto dentro** (lo que ves en la caja) | **Sí**, se envía tal cual |
| Un renglón «Ejemplo: `algo`» debajo del campo | **No**, es solo una pista |
| Una casilla marcada | Sí, añade su opción (`--todos`, `--mostrar`…) |

Además, cada formulario tiene abajo una **vista previa** que muestra el comando exacto
que se va a ejecutar con lo que hay escrito. Si en la vista previa no aparece un dato,
ese dato no se enviará. Es la forma más rápida de comprobar que el comando quedó bien.

Los campos obligatorios van con un asterisco rojo; si falta uno, la página no ejecuta
nada y dice qué falta (por ejemplo, «Indique «Video (.mp4)» o «Cámara en vivo»»).

### Qué se rellena solo y qué es solo un ejemplo

| Acción | Se rellena automáticamente | Solo trae ejemplo (no se envía) |
|---|---|---|
| Verificar el entorno | Video, GPX, Pesos | — |
| Procesar un recorrido | Video, GPX, Pesos | Región, Procesar 1 de cada N, Máximo de fotogramas, Hora de inicio, Cámara |
| Resumen por clase | Base de datos | Recorrido |
| Exportar a CSV | Base de datos | Recorrido, Archivo CSV |
| Regenerar el mapa | Base de datos | Recorrido, Archivo HTML |
| Fusionar daños repetidos | Base de datos, Radio (8 m) | — |
| Métricas de campo | Base de datos, Radio (10 m) | Verdad de campo |
| Error de área y posición | Base de datos, Radio (10 m) | Huecos medidos (**obligatorio**) |
| Calibrar la cámara | Segundo (0), Archivo .npy | Video, Imagen, Ancho, Largo, Rotación, Esquinas |
| Generar la demo sintética | Carpeta de imágenes, Carpeta de destino | Nº de imágenes, Hora, fps |
| Preparar RDD2022 | Origen, Destino, Países | — |
| Combinar datasets | Carpeta de salida | Datasets de entrada (**obligatorio**), Repetir |
| Entrenar el modelo | data.yaml, Pesos iniciales | Épocas, Tamaño, Lote, Dispositivo, Proyecto, Nombre, Destino |

«Se rellena automáticamente» significa que se toma de lo que ya existe en el proyecto:
el primer video de `datos/videos/`, el **GPX que coincide en hora** con ese video, los
pesos de `modelos/` y la **base de datos con más daños** (la de la campaña real, no una
corrida de prueba). Si no existe nada, el campo queda vacío y hay que escribirlo o
elegirlo de la lista desplegable.

## 3. Procesar: el flujo recomendado

1. **Verificar el entorno** — confirma que están el modelo, la calibración, el video y el
   GPX, y avisa si el video y el GPX no coinciden en hora. Es rápido.
2. **Procesar un recorrido** — con el video y el GPX rellenos, pulse *Ejecutar*. Tarda
   unos minutos; la página del trabajo muestra el avance y las rutas de salida.
   - Para una prueba rápida, escriba 60 en «Máximo de fotogramas».
   - Para un video vertical (como los de la campaña), escriba `0,0.45,1,1` en «Región».
3. **Salidas** → abra el **Mapa** o los videos anotados de esa carpeta.
4. **Revisar** → marque cada recorte como real o falso positivo.
5. **Métricas de campo** → calcule la precisión con lo que acaba de revisar.

## 4. Datos y modelo (tutorial paso a paso)

Estas son las funciones que normalmente se hacen por consola, en Colab o con scripts. El
orden importa:

### Preparar RDD2022
Convierte los ZIP de `datos/RDD2022/` al formato YOLO en `datos/rdd_yolo/`, con las cuatro
clases del proyecto (`D00`, `D10`, `D20`, `D40`) y una división 80/10/10. Deja un 10 % de
imágenes sin daños como negativos. **Tarda varios minutos.** Es el primer paso: sin esto
no hay demo sintética ni entrenamiento. Los países ya vienen rellenados con los cinco del
plan; quite los que no quiera.

### Generar la demo sintética
Arma un video (`datos/demo/VID_….mp4`) y un GPX simulado con imágenes del dataset, para
correr *Procesar* sin recorridos reales. Es la **demo de respaldo** para la presentación.
Necesita que exista la carpeta `datos/rdd_yolo/images/test`, así que ejecute antes
*Preparar RDD2022*. Cuando termine, vaya a *Procesar* y use el video y el GPX que quedaron
en `datos/demo/`.

### Combinar datasets
Une el RDD2022 convertido con la exportación de Roboflow de Montería (`datos/monteria/`)
en `datos/combinado/`, sobremuestreando las fotos locales. **Hoy no se puede ejecutar:**
falta `datos/monteria/` (issue #6). Es el requisito de la fase 2 del modelo.

### Calibrar la cámara
Calcula la homografía que convierte píxeles en metros, para que el área de los daños deje
de estar solo en píxeles. Necesita un video o una foto con un rectángulo de medidas
conocidas (marcas viales o conos). Rellene «Ancho real» y «Largo real» en metros.
- Si escribe las cuatro esquinas en «Esquinas del rectángulo»
  (`x1,y1;x2,y2;x3,y3;x4,y4`), no abre ninguna ventana.
- Si lo deja vacío, abre una ventana de OpenCV **en el equipo donde corre el servidor**
  para marcarlas con el ratón.
- Resultado: `calibracion/homografia.npy`. A partir de ahí, `config.yaml` la usa sola y
  los daños nuevos tendrán `area_m2`.

### Entrenar el modelo
Entrena o ajusta el detector. Por defecto usa `datos/rdd_yolo/data.yaml`, que ya está
escrito, y guarda la corrida donde le diga «Proyecto» y «Nombre». **No es para el
portátil**: sin GPU puede tardar horas, y necesita Ultralytics instalado
(`pip install -e ".[yolo]"`). Lo normal es usar el notebook de Colab
(`notebooks/entrenamiento_colab.ipynb`), que hace lo mismo con GPU.

## 5. Revisar sin ventanas

`tapahuecos revisar` abre una ventana de OpenCV y no funciona en Colab ni en un servidor.
La página **Revisar** lo reemplaza: muestra una galería con los recortes y dos botones,
*Real* y *Falso*. Cada clic se guarda en la misma base de datos, y arriba se actualizan
los contadores y la precisión. El filtro «Pendientes / Todos» y el de clase ayudan a
revisar por lotes.

## 6. El mapa y los mosaicos (error 403)

El mapa HTML usa mosaicos de un proveedor externo. OpenStreetMap **bloquea sus servidores
voluntarios** si la página se abre muchas veces («403 Access blocked … tile usage
policy») y el mapa de CARTO ahora exige clave de API, así que el proyecto usa por defecto
el mapa de calles de **Esri**, que no pide clave. Se cambia en `config.yaml`:

```yaml
mapa:
  tiles: "Esri.WorldStreetMap"   # o "Esri.WorldImagery" (satélite), "OpenTopoMap",
                                 # "OpenStreetMap", o una URL propia con {z}/{x}/{y}
```

Si un mapa viejo da 403, regenérelo con *Regenerar el mapa* (o `tapahuecos mapa`). El mapa
necesita internet; sin conexión se ven los puntos, pero no las calles.

## 7. Problemas comunes

| Síntoma | Qué hacer |
|---|---|
| «Falta «Video (.mp4)»» | El campo quedó vacío: escríbalo o elíjalo de la lista. No basta el «Ejemplo». |
| «No existe «ruta»» | Revise la ruta: se busca desde la carpeta del proyecto. |
| El trabajo termina con error | Mire la última línea de la salida: es el mismo mensaje que daría la consola. |
| El mapa sale con cuadros grises | Sin internet o mosaicos bloqueados: vea la sección 6. |
| El GPX no coincide | Pulse *Buscar el GPX del video* o ejecute *Verificar el entorno*, que avisa del desajuste. |
