# Contratos entre módulos

Lo que cada etapa del paquete `src/tapahuecos/` recibe y entrega. Mientras estas firmas no cambien, cada módulo se puede modificar por separado sin romper a los demás. **Cambiar algo de este documento es un cambio de contrato**: va en un Pull Request aparte y se avisa al equipo antes (ver [CONTRIBUTING.md](../CONTRIBUTING.md)).

```
entrada.py → detector.py → segmentacion.py + medicion.py → gps.py → registro.py → salidas.py
                              (orquestado por pipeline.py, expuesto en cli.py)
```

## Convenciones

| Qué | Convención |
|---|---|
| Recuadros | `(x1, y1, x2, y2)` en píxeles enteros de Python (no `numpy.int64`: SQLite no los acepta), en coordenadas del fotograma completo salvo que se diga otra cosa |
| Imágenes | `np.ndarray` BGR `uint8` (OpenCV) |
| Máscaras | `np.ndarray` `uint8` 2D, 255 = daño, 0 = fondo |
| Tiempo en el video | `float`, segundos desde el primer fotograma |
| Instantes | `datetime` **con zona horaria**; en la base de datos se guardan en UTC (ISO 8601) |
| Coordenadas | `(latitud, longitud)` en grados decimales WGS84 |
| Valor desconocido | `None` (sin GPS, sin calibración, sin ID de seguimiento): nunca `0` ni `NaN` |
| Parámetros ajustables | En `config.yaml` / `config.py`, no fijos en el código |

## Clases de daño — `clases.py`

| Código | Nombre | Segmentación |
|---|---|---|
| D00 | Grieta longitudinal | línea |
| D10 | Grieta transversal | línea |
| D20 | Piel de cocodrilo | malla |
| D40 | Hueco | región |

- `CLASES: tuple[ClaseDano, ...]`, `CODIGOS: tuple[str, ...]`.
- `ClaseDano(codigo, nombre, descripcion, color_bgr, color_hex)`, inmutable.
- `clase_por_codigo(codigo) -> ClaseDano`: si el modelo trae un nombre que no es de RDD2022 (p. ej. `person`), devuelve una clase genérica con color propio; esas clases se dibujan pero **no se segmentan**.
- Los criterios para etiquetar cada clase están en la [guía de etiquetado](guia_etiquetado.md).

## 1. Entrada — `entrada.py`

```python
@dataclass
class Fotograma:
    indice: int        # posición en el video, empezando en 0 (cuenta también los saltados)
    tiempo_s: float    # segundos desde el inicio del video
    imagen: np.ndarray

FuenteVideo(origen: str | Path | int, rotacion: int = 0)   # int = cámara; rotacion ∈ {0, 90, 180, 270}
    .fotogramas(cada_n: int = 1) -> Iterator[Fotograma]
    .fps: float; .total: int; .duracion_s: float; .es_camara: bool
    # gestor de contexto: `with FuenteVideo(...) as fuente:`

resolver_inicio(ruta_video, inicio_config, utc_offset_horas, duracion_s=0.0) -> datetime | None
```

- `tiempo_s` usa la marca del fotograma si es fiable (celulares con tasa variable) y si no `indice / fps`.
- La hora de inicio se toma, en este orden: configuración o `--inicio` → nombre del archivo (`VID_20261029_143015.mp4`) → fecha de modificación menos la duración.

## 2. Detección — `detector.py`

```python
@dataclass
class Deteccion:
    caja: tuple[int, int, int, int]   # x1, y1, x2, y2
    clase: ClaseDano
    confianza: float                  # 0–1
    track_id: int | None              # None mientras ByteTrack no confirma el objeto

Detector(cfg: ConfigModelo).rastrear(imagen: np.ndarray) -> list[Deteccion]
```

- `caja` viene en coordenadas de la imagen recibida; `pipeline.py` la lleva al fotograma completo cuando se usa `region`.
- Cualquier objeto con un método `rastrear(imagen) -> list[Deteccion]` sirve como detector (`pipeline.DetectorProtocolo`). Así se prueba sin YOLO.
- Ultralytics se importa dentro de `Detector.__init__`: el resto del paquete no debe importarlo.

## 3a. Segmentación — `segmentacion.py`

```python
@dataclass
class Segmentacion:
    mascara: np.ndarray          # mismo alto y ancho que el recorte
    contornos: list[np.ndarray]  # en coordenadas del recorte
    area_px: int                 # propiedad: píxeles en 255 de la máscara

segmentar(recorte: np.ndarray, codigo_clase: str, cfg: ConfigSegmentacion) -> Segmentacion
```

- Recibe **solo el recorte** del recuadro, no el fotograma.
- Si no encuentra daño (superficie uniforme, recorte menor de 3 px, clase no estándar) devuelve máscara en cero y `contornos == []`; nunca lanza excepción.

## 3b. Medición — `medicion.py`

```python
Medidor(homografia: np.ndarray | None = None, metros_por_pixel: float | None = None)
Medidor.desde_config(cfg: ConfigCalibracion) -> Medidor
    .calibrado: bool
    .area_m2(contornos: list[np.ndarray]) -> float | None   # contornos en coordenadas del fotograma completo
```

- La homografía (3×3, imagen → suelo en metros) se genera con `scripts/calibrar_homografia.py` y se guarda en `calibracion/homografia.npy`.
- Sin calibración, `area_m2` devuelve `None` y el área queda solo en píxeles.

## 4. Georreferenciación — `gps.py`

```python
Recorrido.desde_gpx(ruta) -> Recorrido
    .posicion(instante: datetime, tolerancia_s: float = 5.0) -> tuple[float, float] | None
    .inicio: datetime; .fin: datetime

distancia_m(lat1, lon1, lat2, lon2) -> float   # haversine
```

- `posicion` interpola linealmente entre los dos puntos vecinos. Devuelve `None` fuera del recorrido (más la tolerancia) o en un hueco largo del GPS.
- El instante de cada fotograma es `inicio_video + tiempo_s + desfase_gps_s`.

## 5. Registro — `registro.py`

```python
@dataclass
class Observacion:     # un daño visto en un fotograma
    track_id: int; clase: ClaseDano; confianza: float
    fotograma: int; tiempo_video_s: float; instante_utc: datetime | None
    latitud: float | None; longitud: float | None
    area_px: int; area_m2: float | None
    caja: tuple[int, int, int, int]; recorte: np.ndarray

GestorDanos(bd, recorrido_id, carpeta_recortes, min_fotogramas=3, max_ausencia=30)
    .observar(obs); .cerrar_ausentes(fotograma_actual); .finalizar() -> int

BaseDatos(ruta)   # SQLite; gestor de contexto
    .nuevo_recorrido(video, gpx, modelo) -> int
    .danos(recorrido_id=None) -> list[dict]
    .marcar(dano_id, real); .asignar_grupos(grupos)
```

Reglas del registro:

- **Un registro por `track_id` y recorrido**, con la observación de **mayor confianza** (`UNIQUE (recorrido_id, track_id)`).
- Solo se registra si el daño se vio en al menos `min_fotogramas` fotogramas (filtra detecciones espurias).
- Un daño se cierra cuando lleva más de `max_ausencia` fotogramas sin verse, o al terminar el video.
- Las detecciones sin `track_id` se dibujan pero no se registran.
- El recorte se guarda como `recortes/{recorrido:03d}_{track:05d}_{clase}.jpg` y en la BD va su ruta **relativa a la carpeta de la BD**.

## 6. Salidas — `salidas.py`

```python
dibujar_deteccion(imagen, det, mascara=None, area_m2=None) -> None   # dibuja sobre `imagen`
dibujar_cabecera(imagen, texto) -> None
EscritorVideo(ruta, fps).escribir(imagen); .cerrar()                 # el tamaño lo fija el primer fotograma
generar_mapa(filas, ruta_html, carpeta_base) -> Path
exportar_csv(filas, ruta) -> Path                                    # UTF-8 con BOM, para Excel
resumen(filas) -> pandas.DataFrame
```

### Columnas del CSV (`danos.csv`)

Son las de `BaseDatos.danos()`, en este orden:

| Columna | Tipo | Notas |
|---|---|---|
| `id` | int | |
| `recorrido_id` | int | |
| `track_id` | int | ID de ByteTrack dentro del recorrido |
| `clase`, `nombre_clase` | str | `D40`, `Hueco` |
| `confianza` | float | la mayor observada |
| `veces_visto` | int | fotogramas en que apareció |
| `fotograma`, `tiempo_video_s` | int, float | de la observación guardada |
| `instante_utc` | str \| vacío | ISO 8601 en UTC |
| `latitud`, `longitud` | float \| vacío | vacío si no hubo GPS |
| `area_px` | int | |
| `area_m2` | float \| vacío | vacío sin calibración |
| `x1`, `y1`, `x2`, `y2` | int | recuadro en el fotograma completo |
| `recorte` | str | ruta relativa a la carpeta de la BD |
| `verificado` | 1 \| 0 \| vacío | real / falso positivo / sin revisar (`tapahuecos revisar`) |
| `grupo` | int \| vacío | mismo daño en varios recorridos (`tapahuecos fusionar`) |
| `video` | str | ruta del video de origen |

`tests/test_main.py` verifica este conjunto de columnas.

## Orquestación — `pipeline.py` y `cli.py`

```python
procesar(origen: Path | int, cfg: Config, carpeta_salida: Path, ruta_gpx: Path | None = None,
         mostrar: bool = False, detector: DetectorProtocolo | None = None) -> Resultado
```

`tapahuecos procesar --video V [--gpx G] [--config C] [--salida S] [--pesos P] [--cada N] [--inicio ISO] [--region X1,Y1,X2,Y2]` deja en `S`:

| Archivo | Contenido |
|---|---|
| `<video>_anotado.mp4` | video con máscaras, recuadros y cabecera de tiempo/GPS |
| `recortes/*.jpg` | un recorte por daño registrado |
| `danos.db` | base de datos SQLite (acumula recorridos) |
| `danos.csv` | todos los daños de la BD |
| `mapa.html` | mapa Folium, una capa por clase, un punto por daño único |

Otros comandos: `mapa`, `fusionar`, `exportar`, `resumen`, `revisar`. El código de salida es `0` si todo salió bien y `1` ante archivos inexistentes o parámetros inválidos.

## Datos de prueba — `tests/fixtures/generar.py`

`generar(carpeta) -> dict[str, Path]` crea un video sintético con un hueco (`video`), una imagen (`imagen`), un GPX recto en Montería (`gpx`) y un CSV de verdad de campo (`verdad`, columnas `latitud,longitud,clase`). Las pruebas lo usan con la fixture `datos_prueba` de `tests/conftest.py`. Si un módulo nuevo necesita otros datos de prueba, se agregan aquí.
