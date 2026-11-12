"""Ejecuta los comandos del proyecto como trabajos en segundo plano.

Cada trabajo lanza un subproceso (`python -u ...`) y guarda su salida línea a línea.
El navegador consulta el estado cada segundo, así una tarea larga (por ejemplo
`procesar`, que tarda minutos) no bloquea el servidor ni la página.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from tapahuecos.web.acciones import Accion, mostrar_comando

MAX_LINEAS = 3000  # tope de memoria por trabajo; se conservan las últimas
ESPERA_CANCELAR_S = 5.0  # tras pedir que termine, se mata el proceso si sigue vivo


class TrabajoEnCurso(RuntimeError):
    """Ya hay un trabajo de la misma acción corriendo; lanzar otro chocaría con él."""

    def __init__(self, trabajo: Trabajo):
        super().__init__(f"ya hay un «{trabajo.accion_nombre}» en curso")
        self.trabajo = trabajo


class Trabajo:
    """Un comando en ejecución o ya terminado, con su salida acumulada."""

    def __init__(self, accion: Accion, argv: list[str]):
        self.id = uuid.uuid4().hex[:12]
        self.accion_id = accion.id
        self.accion_nombre = accion.nombre
        self.comando = ["python", *argv]
        self.estado = "en_curso"  # en_curso | terminado | error | cancelado
        self.codigo: int | None = None
        self.inicio = time.time()
        self.fin: float | None = None
        self._lineas: list[str] = []
        self._descartadas = 0  # líneas viejas que se borraron por el tope de MAX_LINEAS
        self._lock = threading.Lock()
        self._proceso: subprocess.Popen | None = None
        self.cancelado = False

    def asignar_proceso(self, proceso: subprocess.Popen) -> None:
        with self._lock:
            self._proceso = proceso
            cancelar_ya = self.cancelado  # se pidió cancelar antes de que arrancara
        if cancelar_ya:
            self._terminar(proceso)

    def cancelar(self) -> bool:
        """Pide al proceso que termine. Devuelve False si el trabajo ya había terminado."""
        with self._lock:
            if self.estado != "en_curso":
                return False
            self.cancelado = True
            proceso = self._proceso
        if proceso is not None:
            self._terminar(proceso)
        return True

    @staticmethod
    def _terminar(proceso: subprocess.Popen) -> None:
        if proceso.poll() is not None:
            return
        proceso.terminate()

        def rematar() -> None:
            try:
                proceso.wait(timeout=ESPERA_CANCELAR_S)
            except subprocess.TimeoutExpired:
                proceso.kill()

        threading.Thread(target=rematar, daemon=True).start()

    def agregar(self, linea: str) -> None:
        with self._lock:
            self._lineas.append(linea)
            sobrantes = len(self._lineas) - MAX_LINEAS
            if sobrantes > 0:
                del self._lineas[:sobrantes]
                self._descartadas += sobrantes

    def leer(self, indice: int) -> tuple[list[str], int]:
        """Líneas desde el índice absoluto `indice` y el total emitido, en una sola lectura.

        Los índices cuentan todas las líneas emitidas, también las que ya se descartaron
        por el tope; así el navegador sigue recibiendo salida aunque se pase de MAX_LINEAS.
        """
        with self._lock:
            inicio = max(0, indice - self._descartadas)
            return self._lineas[inicio:], self._descartadas + len(self._lineas)

    def desde(self, indice: int) -> list[str]:
        return self.leer(indice)[0]

    def instantanea(self) -> dict:
        with self._lock:
            total = self._descartadas + len(self._lineas)
        return {
            "id": self.id,
            "accion": self.accion_nombre,
            "comando": mostrar_comando(self.comando),
            "estado": self.estado,
            "codigo": self.codigo,
            "total": total,
            "segundos": round((self.fin or time.time()) - self.inicio, 1),
        }


class Ejecutor:
    """Cola de trabajos. Conserva los últimos para poder volver a verlos."""

    def __init__(self, raiz: Path, max_trabajos: int = 30):
        self.raiz = Path(raiz)
        self.max_trabajos = max_trabajos
        self._trabajos: dict[str, Trabajo] = {}
        self._orden: list[str] = []
        self._lock = threading.Lock()

    def iniciar(self, accion: Accion, valores: dict[str, str]) -> Trabajo:
        """Lanza la acción. TrabajoEnCurso si ya corre otra igual.

        Dos `procesar` (o dos `entrenar`) a la vez escribirían en la misma carpeta y en
        el mismo danos.db; el botón del navegador se desactiva, pero eso no basta si se
        abre otra pestaña o se recarga la página.
        """
        argv = accion.argv(valores)
        trabajo = Trabajo(accion, argv)
        with self._lock:
            for otro in self._trabajos.values():
                if otro.accion_id == accion.id and otro.estado == "en_curso":
                    raise TrabajoEnCurso(otro)
            self._trabajos[trabajo.id] = trabajo
            self._orden.append(trabajo.id)
            self._recortar()
        threading.Thread(target=self._correr, args=(trabajo, argv), daemon=True).start()
        return trabajo

    def _recortar(self) -> None:
        """Olvida los trabajos terminados más viejos; los que siguen en curso no se tocan."""
        terminados = [i for i in self._orden if self._trabajos[i].estado != "en_curso"]
        while len(self._orden) > self.max_trabajos and terminados:
            viejo = terminados.pop(0)
            self._orden.remove(viejo)
            self._trabajos.pop(viejo, None)

    def cancelar(self, trabajo_id: str) -> bool:
        trabajo = self.obtener(trabajo_id)
        return trabajo is not None and trabajo.cancelar()

    def _correr(self, trabajo: Trabajo, argv: list[str]) -> None:
        entorno = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            proceso = subprocess.Popen(
                [sys.executable, "-u", *argv],
                cwd=str(self.raiz),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=entorno,
            )
        except OSError as error:
            trabajo.agregar(f"No se pudo iniciar el comando: {error}")
            trabajo.estado = "error"
            trabajo.codigo = -1
            trabajo.fin = time.time()
            return
        trabajo.asignar_proceso(proceso)
        assert proceso.stdout is not None
        for linea in proceso.stdout:
            trabajo.agregar(linea.rstrip("\r\n"))
        codigo = proceso.wait()
        trabajo.codigo = codigo
        if codigo == 0:
            trabajo.estado = "terminado"
        elif trabajo.cancelado:
            trabajo.agregar("— Cancelado desde la interfaz —")
            trabajo.estado = "cancelado"
        else:
            trabajo.estado = "error"
        trabajo.fin = time.time()

    def obtener(self, trabajo_id: str) -> Trabajo | None:
        with self._lock:
            return self._trabajos.get(trabajo_id)

    def recientes(self, limite: int = 6) -> list[Trabajo]:
        with self._lock:
            ids = list(reversed(self._orden))[:limite]
            return [self._trabajos[i] for i in ids if i in self._trabajos]
