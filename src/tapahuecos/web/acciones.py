"""Catálogo de acciones que la interfaz web puede ejecutar.

Cada acción se declara una sola vez aquí y de ahí salen el formulario, la vista previa
del comando y la línea de comandos que se ejecuta. Todas reutilizan lo que ya existe:
los comandos de `tapahuecos` y los scripts de `scripts/`.

Campos: `valor` es un valor por defecto **real** (se envía al comando); `marcador` es
solo un ejemplo que se muestra como ayuda y **nunca** se envía; `automatico` rellena el
campo con lo que ya existe en el proyecto (el primer video, el GPX que coincide, etc.).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass

# Tipos de campo: texto, numero, casilla (--flag) y lista (varios valores separados).
TIPOS = ("texto", "numero", "casilla", "lista")


@dataclass(frozen=True)
class Campo:
    nombre: str  # es también el nombre de la opción de la CLI, sin los guiones
    etiqueta: str
    tipo: str = "texto"
    ayuda: str = ""
    requerido: bool = False
    existe: bool = False  # si trae valor, la ruta debe existir
    automatico: str = ""  # nombre de la sugerencia con la que se rellena (video, gpx_del_video…)
    marcador: str = ""  # ejemplo; solo se muestra, no se envía
    valor: str = ""  # valor por defecto real; sí se envía

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(f"tipo de campo desconocido: {self.tipo}")


@dataclass(frozen=True)
class Accion:
    id: str
    nombre: str
    descripcion: str
    grupo: str
    comando: tuple[str, ...]
    campos: tuple[Campo, ...] = ()
    nota: str = ""
    # Exige que exactamente uno de estos campos tenga valor (p. ej. --video o --camara:
    # la CLI rechaza los dos a la vez).
    requiere_uno_de: tuple[str, ...] = ()

    def campo(self, nombre: str) -> Campo | None:
        return next((c for c in self.campos if c.nombre == nombre), None)

    def argv(self, valores: dict[str, str]) -> list[str]:
        """Traduce el formulario a la lista de argumentos del comando."""
        argv = list(self.comando)
        for campo in self.campos:
            valor = (valores.get(campo.nombre) or "").strip()
            if campo.tipo == "casilla":
                if valor.lower() in ("1", "true", "on", "si", "sí"):
                    argv.append(f"--{campo.nombre}")
                continue
            if not valor:
                continue
            argv.append(f"--{campo.nombre}")
            if campo.tipo == "lista":
                argv.extend(partes_de_lista(valor))
            else:
                argv.append(valor)
        return argv


def partes_de_lista(valor: str) -> list[str]:
    """Los valores de un campo de tipo lista.

    Normalmente van separados por comas o espacios. Si el texto trae «;» (o saltos de
    línea), se separa solo por ahí, para admitir rutas con espacios como
    `C:/Users/Juan Pérez/rdd_yolo; datos/monteria`.
    """
    separador = r"[;\n]+" if re.search(r"[;\n]", valor) else r"[,\s]+"
    return [parte.strip() for parte in re.split(separador, valor.strip()) if parte.strip()]


def mostrar_comando(argv: list[str]) -> str:
    """El comando como se escribiría en la consola, con comillas donde hagan falta."""
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


RECORRIDO = Campo("recorrido", "Recorrido", tipo="numero",
                  ayuda="Limitar a un recorrido (columna recorrido_id); vacío = todos")


def _radio(valor: str = "10") -> Campo:
    return Campo("radio", "Radio (m)", tipo="numero", valor=valor,
                 ayuda="Distancia para considerar que dos daños son el mismo")


def _db() -> Campo:
    return Campo("db", "Base de datos", automatico="db", existe=True,
                 ayuda="Ruta del danos.db, relativa a la carpeta del proyecto",
                 marcador="salidas/Prueba_region/danos.db")


def _pesos() -> Campo:
    return Campo("pesos", "Pesos (.pt)", automatico="pesos", existe=True,
                 ayuda="Modelo YOLO entrenado", marcador="modelos/best_rdd.pt")


def _video(ayuda: str = "Video grabado desde el vehículo") -> Campo:
    return Campo("video", "Video (.mp4)", automatico="video", existe=True, ayuda=ayuda,
                 marcador="datos/videos/VID_20261108_110401.mp4")


def _gpx() -> Campo:
    return Campo("gpx", "Recorrido GPS (.gpx)", automatico="gpx_del_video", existe=True,
                 ayuda="Se rellena con el GPX que coincide en hora con el video; "
                       "si no hay, use el botón para buscarlo o déjelo vacío "
                       "(los daños quedarán sin coordenadas)",
                 marcador="datos/gpx/20261108-110358.gpx")


ACCIONES: tuple[Accion, ...] = (
    # ------------------------------------------------------------------ Procesar
    Accion(
        id="verificar",
        nombre="Verificar el entorno",
        descripcion="Comprueba dependencias, modelo, calibración y, si se indican, el video "
                    "y el GPX (incluido su solape temporal). No carga YOLO y es rápido: "
                    "conviene ejecutarlo antes de procesar.",
        grupo="Procesar",
        comando=("-m", "tapahuecos", "verificar"),
        campos=(_video(), _gpx(), _pesos(),
                Campo("inicio", "Hora de inicio",
                      ayuda="La misma que usará en «Procesar», si el nombre del video no trae la hora",
                      marcador="2026-11-08T11:04:01"),
                Campo("region", "Región de interés", ayuda="La misma que usará en «Procesar»",
                      marcador="0,0.45,1,1")),
    ),
    Accion(
        id="procesar",
        nombre="Procesar un recorrido",
        descripcion="Genera el video anotado, los recortes, la base de datos, el CSV y el mapa. "
                    "Es la acción más pesada: en CPU tarda unos minutos por recorrido.",
        grupo="Procesar",
        comando=("-m", "tapahuecos", "procesar"),
        campos=(
            _video(),
            _gpx(),
            Campo("salida", "Carpeta de salida", valor="salidas"),
            _pesos(),
            Campo("region", "Región de interés",
                  ayuda="x1,y1,x2,y2 en fracciones. Para un video vertical, la franja de la vía",
                  marcador="0,0.45,1,1"),
            Campo("cada", "Procesar 1 de cada N", tipo="numero",
                  ayuda="Más alto = más rápido. Vacío = lo que diga config.yaml (2)",
                  marcador="2"),
            Campo("max-fotogramas", "Máximo de fotogramas", tipo="numero",
                  ayuda="Prueba rápida: se detiene tras N fotogramas", marcador="60"),
            Campo("inicio", "Hora de inicio",
                  ayuda="Solo si el nombre del video no trae la hora", marcador="2026-11-08T11:04:01"),
            Campo("camara", "Cámara en vivo", tipo="numero",
                  ayuda="Índice de cámara (0 = la del equipo). Abre una ventana en el servidor",
                  marcador="0"),
            Campo("mostrar", "Mostrar el video mientras procesa", tipo="casilla",
                  ayuda="Abre una ventana; no sirve si el servidor no tiene pantalla"),
        ),
        nota="Indique «Video» o «Cámara en vivo». Con video real, use antes «Verificar el entorno».",
        requiere_uno_de=("video", "camara"),
    ),
    # -------------------------------------------------------------- Base de datos
    Accion(
        id="resumen",
        nombre="Resumen por clase",
        descripcion="Tabla con la cantidad, el área media, el porcentaje con GPS y la revisión.",
        grupo="Base de datos",
        comando=("-m", "tapahuecos", "resumen"),
        campos=(_db(), RECORRIDO),
    ),
    Accion(
        id="exportar",
        nombre="Exportar a CSV",
        descripcion="Vuelca la base de datos a un CSV (UTF-8 con BOM, para Excel).",
        grupo="Base de datos",
        comando=("-m", "tapahuecos", "exportar"),
        campos=(_db(), RECORRIDO,
                Campo("csv", "Archivo CSV", ayuda="Vacío = danos.csv junto a la base de datos")),
    ),
    Accion(
        id="mapa",
        nombre="Regenerar el mapa",
        descripcion="Rehace el mapa HTML desde la base de datos, con el proveedor de mosaicos "
                    "de config.yaml (mapa.tiles).",
        grupo="Base de datos",
        comando=("-m", "tapahuecos", "mapa"),
        campos=(_db(), RECORRIDO,
                Campo("salida", "Archivo HTML", ayuda="Vacío = mapa.html junto a la base de datos"),
                Campo("todos", "Un punto por registro", tipo="casilla",
                      ayuda="Sin agrupar los daños repetidos entre recorridos")),
    ),
    Accion(
        id="fusionar",
        nombre="Fusionar daños repetidos",
        descripcion="Agrupa el mismo daño registrado en varios recorridos (misma clase y cerca).",
        grupo="Base de datos",
        comando=("-m", "tapahuecos", "fusionar"),
        campos=(_db(), Campo("radio", "Radio (m)", tipo="numero", valor="8"),
                Campo("cualquier-clase", "Agrupar aunque cambie la clase", tipo="casilla")),
    ),
    # ------------------------------------------------------------------- Reportes
    Accion(
        id="evaluar-campo",
        nombre="Métricas de campo",
        descripcion="Precisión con los daños revisados a mano y, si hay verdad de campo, "
                    "exhaustividad y F1. Regenera reportes/campo.md y .json.",
        grupo="Reportes",
        comando=("scripts/evaluar.py", "campo"),
        campos=(_db(),
                Campo("verdad", "Verdad de campo (.csv)", existe=True,
                      ayuda="Opcional. Columnas latitud,longitud[,clase]",
                      marcador="datos/verdad_campo.csv"),
                _radio(valor="10"),
                Campo("misma-clase", "Exigir la misma clase", tipo="casilla")),
    ),
    Accion(
        id="evaluar-area",
        nombre="Error de área y posición",
        descripcion="Empareja cada hueco medido con el D40 más cercano y calcula los errores. "
                    "Guarda la tabla y un gráfico.",
        grupo="Reportes",
        comando=("scripts/evaluar.py", "area"),
        campos=(_db(),
                Campo("medidos", "Huecos medidos (.csv)", requerido=True, existe=True,
                      ayuda="Obligatorio. Columnas latitud,longitud,largo_m,ancho_m,area_m2,foto",
                      marcador="datos/huecos_medidos.csv"),
                _radio(valor="10")),
        nota="Necesita el CSV de huecos medidos con cinta, que todavía no existe en el "
             "proyecto; ver la issue #27.",
    ),
    # ------------------------------------------------------------ Datos y modelo
    Accion(
        id="calibrar",
        nombre="Calibrar la cámara",
        descripcion="Calcula la homografía para pasar de píxeles a metros. Sin ella, el área "
                    "de los daños queda solo en píxeles.",
        grupo="Datos y modelo",
        comando=("scripts/calibrar_homografia.py",),
        campos=(Campo("video", "Video de calibración", existe=True,
                      ayuda="Indique «Video» o «Imagen»",
                      marcador="datos/videos/calibracion.mp4"),
                Campo("imagen", "Imagen de calibración", existe=True,
                      marcador="calibracion/fotograma.png"),
                Campo("ancho", "Ancho real (m)", tipo="numero", requerido=True, marcador="3"),
                Campo("largo", "Largo real (m)", tipo="numero", requerido=True, marcador="5"),
                Campo("segundo", "Segundo del video", tipo="numero", valor="0"),
                Campo("rotacion", "Rotación", tipo="numero",
                      ayuda="0, 90, 180 o 270; el mismo valor de video.rotacion", marcador="0"),
                Campo("puntos", "Esquinas del rectángulo",
                      ayuda="'x1,y1;x2,y2;x3,y3;x4,y4' para no abrir ventana",
                      marcador="0,0;100,0;100,100;0,100"),
                Campo("salida", "Archivo .npy", valor="calibracion/homografia.npy")),
        nota="Sin «Esquinas del rectángulo» abre una ventana de OpenCV en el servidor para "
             "marcarlas con el ratón. Mejor escribirlas si el servidor no tiene pantalla.",
        requiere_uno_de=("video", "imagen"),
    ),
    Accion(
        id="demo",
        nombre="Generar la demo sintética",
        descripcion="Arma un video y un GPX de demostración con imágenes (por ejemplo, RDD2022) "
                    "para correr «Procesar» sin recorridos reales. Es la demo de respaldo.",
        grupo="Datos y modelo",
        comando=("scripts/demo.py",),
        campos=(Campo("imagenes", "Carpeta de imágenes", requerido=True, existe=True,
                      automatico="imagenes",
                      ayuda="Necesita las imágenes ya convertidas a YOLO "
                            "(ejecute antes «Preparar RDD2022»)",
                      marcador="datos/rdd_yolo/images/test"),
                Campo("destino", "Carpeta de destino", valor="datos/demo"),
                Campo("cantidad", "Número de imágenes", tipo="numero", marcador="20"),
                Campo("inicio", "Hora de inicio", marcador="2026-11-29T14:30:00"),
                Campo("fps", "Fotogramas por segundo", tipo="numero", marcador="30")),
    ),
    Accion(
        id="preparar-rdd2022",
        nombre="Preparar RDD2022",
        descripcion="Convierte RDD2022 (Pascal VOC) al formato YOLO con las cuatro clases del "
                    "proyecto y divide en train/val/test. Es pesado (unos minutos).",
        grupo="Datos y modelo",
        comando=("scripts/preparar_rdd2022.py",),
        campos=(Campo("origen", "Carpeta RDD2022", requerido=True, existe=True,
                      valor="datos/RDD2022"),
                Campo("destino", "Carpeta de salida", requerido=True, valor="datos/rdd_yolo"),
                Campo("paises", "Países", tipo="lista",
                      ayuda="Separados por espacios o comas",
                      valor="Japan India Czech United_States China_MotorBike")),
        nota="Deja las imágenes listas para «Generar la demo sintética», «Combinar datasets» y «Entrenar».",
    ),
    Accion(
        id="combinar",
        nombre="Combinar datasets",
        descripcion="Une RDD2022 convertido con la exportación de Roboflow de Montería, "
                    "reordenando las clases.",
        grupo="Datos y modelo",
        comando=("scripts/combinar_datasets.py",),
        campos=(Campo("entradas", "Datasets de entrada", tipo="lista", requerido=True,
                      ayuda="Rutas separadas por espacios; si alguna tiene espacios, "
                            "sepárelas con «;»",
                      marcador="datos/rdd_yolo datos/monteria"),
                Campo("destino", "Carpeta de salida", requerido=True, valor="datos/combinado"),
                Campo("repetir", "Repetir el train", tipo="lista",
                      ayuda="Una vez por dataset, en el mismo orden", marcador="1 3")),
        nota="Falta la exportación de Roboflow de Montería (datos/monteria); sin ella, la "
             "fase 2 del modelo no se puede reproducir (issue #6).",
    ),
    Accion(
        id="entrenar",
        nombre="Entrenar el modelo",
        descripcion="Entrena o ajusta el detector YOLO. Pensado para Google Colab con GPU; "
                    "en un portátil sin GPU puede tardar horas.",
        grupo="Datos y modelo",
        comando=("scripts/entrenar.py",),
        campos=(Campo("datos", "data.yaml", requerido=True, existe=True,
                      valor="datos/rdd_yolo/data.yaml",
                      ayuda="Vacío por defecto el de RDD2022; para la fase 2, datos/combinado/data.yaml"),
                Campo("modelo", "Pesos iniciales", valor="yolov8s.pt",
                      ayuda="yolov8n/s.pt, yolo11n/s.pt o un .pt propio",
                      marcador="modelos/best_rdd.pt"),
                Campo("epocas", "Épocas", tipo="numero", marcador="50"),
                Campo("imgsz", "Tamaño de imagen", tipo="numero", marcador="640"),
                Campo("lote", "Lote", tipo="numero", ayuda="-1 = automático según la GPU",
                      marcador="16"),
                Campo("dispositivo", "Dispositivo", ayuda="'0' para GPU, 'cpu'", marcador="0"),
                Campo("proyecto", "Proyecto (carpeta de la corrida)", marcador="runs"),
                Campo("nombre", "Nombre de la corrida", marcador="rdd_completo"),
                Campo("destino", "Copiar el mejor modelo a", marcador="modelos/best_rdd.pt")),
        nota="Necesita Ultralytics instalado (pip install -e \".[yolo]\") y, de preferencia, "
             "una GPU. Lo normal es ejecutarlo en el notebook de Colab, no en local.",
    ),
)


def por_id(accion_id: str) -> Accion | None:
    return next((a for a in ACCIONES if a.id == accion_id), None)


def por_grupo() -> dict[str, list[Accion]]:
    """Las acciones agrupadas, conservando el orden de declaración."""
    grupos: dict[str, list[Accion]] = {}
    for accion in ACCIONES:
        grupos.setdefault(accion.grupo, []).append(accion)
    return grupos
