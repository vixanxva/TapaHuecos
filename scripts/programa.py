"""Programa de escritorio de TapaHuecos: resultados de la campaña y procesamiento de recorridos.

Una ventana con dos partes:

- Campaña de Montería: la precisión de campo por clase, calculada de la base revisada a mano,
  y botones para abrir el mapa y el video anotado.
- Procesar un recorrido: se elige un video y su GPX, se ve la detección en pantalla y, al
  terminar, se abre el mapa y la carpeta del resultado.

Uso (o doble clic en el acceso directo del escritorio):
    pythonw scripts/programa.py
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from tapahuecos.evaluacion import evaluar_campo  # noqa: E402
from tapahuecos.registro import BaseDatos  # noqa: E402

CAMPANA = RAIZ / "salidas" / "campana_20261108"
VIDEO_DEMO = RAIZ / "datos" / "demo" / "VID_20261104_210159.mp4"
GPX_DEMO = RAIZ / "datos" / "demo" / "VID_20261104_210159_demo.gpx"
SALIDAS = RAIZ / "salidas" / "programa"
COLUMNAS = ("clase", "tipo", "detectados", "reales", "falsos", "precision")


def abrir(ruta: Path) -> None:
    if ruta.suffix == ".html":
        webbrowser.open(ruta.as_uri())
    elif sys.platform == "win32":
        os.startfile(ruta)  # noqa: S606 - programa predeterminado de Windows
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)], check=False)


def filas_por_clase(filas: list[dict]) -> list[tuple]:
    """Una fila por clase: código, nombre, detectados, reales, falsos y precisión."""
    tabla = []
    for clase in sorted({f["clase"] for f in filas}):
        grupo = [f for f in filas if f["clase"] == clase]
        revisados = [f for f in grupo if f["verificado"] is not None]
        reales = sum(f["verificado"] == 1 for f in revisados)
        precision = f"{reales / len(revisados):.2f}" if revisados else "sin revisar"
        tabla.append((clase, grupo[0]["nombre_clase"], len(grupo), reales if revisados else "-",
                      len(revisados) - reales if revisados else "-", precision))
    return tabla


def python_con_consola() -> str:
    """El intérprete para el proceso hijo: python.exe aunque el programa corra con pythonw."""
    ruta = Path(sys.executable)
    candidato = ruta.with_name(ruta.name.replace("pythonw", "python"))
    return str(candidato if candidato.exists() else ruta)


class Programa:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        self.proceso: subprocess.Popen | None = None
        self.detenido = False
        self.salida_actual: Path | None = None
        self.mensajes: queue.Queue[str | int] = queue.Queue()

        raiz.title("TapaHuecos · Detector de daños en las vías")
        raiz.geometry("900x680")
        raiz.minsize(760, 560)
        estilo = ttk.Style()
        if "vista" in estilo.theme_names():
            estilo.theme_use("vista")
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Cifra.TLabel", font=("Segoe UI", 13, "bold"))

        marco = ttk.Frame(raiz, padding=16)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="TapaHuecos", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, text="Video + GPS → daños detectados, medidos y ubicados en un mapa").pack(
            anchor="w", pady=(0, 12))

        self._armar_campana(marco)
        self._armar_proceso(marco)
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.after(150, self._leer_mensajes)

    # --- Campaña ----------------------------------------------------------------------------

    def _armar_campana(self, padre: ttk.Frame) -> None:
        caja = ttk.LabelFrame(padre, text=" Campaña real · Montería, 8 de noviembre de 2026 ",
                              padding=10)
        caja.pack(fill="x")
        if not (CAMPANA / "danos.db").exists():
            ttk.Label(caja, text=f"No se encontró {CAMPANA.relative_to(RAIZ)}").pack(anchor="w")
            return

        with BaseDatos(CAMPANA / "danos.db") as bd:
            filas = bd.danos()
        metricas = evaluar_campo(filas)
        recorridos = len({f["recorrido_id"] for f in filas})
        resumen = ttk.Frame(caja)
        resumen.pack(fill="x")
        precision = f"{metricas.precision:.4f}" if metricas.precision is not None else "-"
        for texto, valor in (("Recorridos", recorridos), ("Daños detectados", len(filas)),
                             ("Revisados a mano", metricas.revisados),
                             ("Daños reales", metricas.reales), ("Precisión de campo", precision)):
            celda = ttk.Frame(resumen)
            celda.pack(side="left", padx=(0, 26))
            ttk.Label(celda, text=texto).pack(anchor="w")
            ttk.Label(celda, text=str(valor), style="Cifra.TLabel").pack(anchor="w")

        self._tabla(caja, filas_por_clase(filas)).pack(fill="x", pady=8)
        botones = ttk.Frame(caja)
        botones.pack(fill="x")
        ttk.Button(botones, text="Abrir mapa", command=lambda: abrir(CAMPANA / "mapa.html")).pack(
            side="left")
        ttk.Button(botones, text="Ver video anotado", command=self._video_campana).pack(
            side="left", padx=8)
        ttk.Label(botones, text="Exhaustividad: sin medir (falta la verdad de campo)").pack(
            side="right")

    def _tabla(self, padre: ttk.Frame, filas: list[tuple]) -> ttk.Treeview:
        tabla = ttk.Treeview(padre, columns=COLUMNAS, show="headings", height=max(len(filas), 1))
        anchos = (60, 200, 90, 70, 70, 90)
        titulos = ("Clase", "Tipo", "Detectados", "Reales", "Falsos", "Precisión")
        for columna, titulo, ancho in zip(COLUMNAS, titulos, anchos, strict=True):
            tabla.heading(columna, text=titulo)
            tabla.column(columna, width=ancho, anchor="w" if columna == "tipo" else "center")
        for fila in filas:
            tabla.insert("", "end", values=fila)
        return tabla

    def _video_campana(self) -> None:
        videos = sorted(CAMPANA.glob("*_anotado.mp4"))
        if videos:
            abrir(videos[0])
        else:
            messagebox.showwarning("TapaHuecos", "No hay videos anotados en la campaña.")

    # --- Procesar ---------------------------------------------------------------------------

    def _armar_proceso(self, padre: ttk.Frame) -> None:
        caja = ttk.LabelFrame(padre, text=" Procesar un recorrido ", padding=10)
        caja.pack(fill="both", expand=True, pady=(12, 0))
        caja.columnconfigure(1, weight=1)

        self.video = tk.StringVar(value=str(VIDEO_DEMO) if VIDEO_DEMO.exists() else "")
        self.gpx = tk.StringVar(value=str(GPX_DEMO) if GPX_DEMO.exists() else "")
        self.mostrar = tk.BooleanVar(value=True)
        for fila, (texto, variable, tipos) in enumerate((
            ("Video", self.video, [("Video", "*.mp4 *.mov *.avi *.mkv")]),
            ("GPX (opcional)", self.gpx, [("Recorrido GPS", "*.gpx")]),
        )):
            ttk.Label(caja, text=texto).grid(row=fila, column=0, sticky="w", pady=2)
            ttk.Entry(caja, textvariable=variable).grid(row=fila, column=1, sticky="ew", padx=6)
            ttk.Button(caja, text="Elegir…",
                       command=lambda v=variable, t=tipos: self._elegir(v, t)).grid(row=fila,
                                                                                   column=2)

        acciones = ttk.Frame(caja)
        acciones.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)
        self.boton_procesar = ttk.Button(acciones, text="Procesar", command=self.procesar)
        self.boton_procesar.pack(side="left")
        self.boton_detener = ttk.Button(acciones, text="Detener", command=self.detener,
                                        state="disabled")
        self.boton_detener.pack(side="left", padx=8)
        ttk.Checkbutton(acciones, text="Ver la detección mientras procesa",
                        variable=self.mostrar).pack(side="left", padx=8)
        self.boton_carpeta = ttk.Button(acciones, text="Abrir carpeta", state="disabled",
                                        command=lambda: abrir(self.salida_actual))
        self.boton_carpeta.pack(side="right")
        self.boton_mapa = ttk.Button(acciones, text="Abrir mapa", state="disabled",
                                     command=lambda: abrir(self.salida_actual / "mapa.html"))
        self.boton_mapa.pack(side="right", padx=8)

        self.barra = ttk.Progressbar(caja, mode="indeterminate")
        self.barra.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.barra.grid_remove()  # solo se ve mientras procesa
        self.registro = tk.Text(caja, height=8, font=("Consolas", 9), state="disabled",
                                wrap="none")
        self.registro.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        caja.rowconfigure(4, weight=1)

    def _elegir(self, variable: tk.StringVar, tipos: list) -> None:
        inicial = Path(variable.get()).parent if variable.get() else RAIZ / "datos"
        ruta = filedialog.askopenfilename(initialdir=inicial, filetypes=tipos)
        if ruta:
            variable.set(ruta)

    def _escribir(self, texto: str) -> None:
        self.registro.configure(state="normal")
        self.registro.insert("end", texto)
        self.registro.see("end")
        self.registro.configure(state="disabled")

    def procesar(self) -> None:
        video = Path(self.video.get().strip())
        gpx = self.gpx.get().strip()
        if not video.is_file():
            messagebox.showerror("TapaHuecos", "Elija un video que exista.")
            return
        if gpx and not Path(gpx).is_file():
            messagebox.showerror("TapaHuecos", "El GPX elegido no existe.")
            return

        # Cada video tiene su carpeta y empieza limpia: el mapa no acumula corridas anteriores.
        self.salida_actual = SALIDAS / video.stem
        if self.salida_actual.exists():
            shutil.rmtree(self.salida_actual)
        argumentos = ["procesar", "--video", str(video), "--salida", str(self.salida_actual),
                      "--config", str(RAIZ / "config.yaml")]
        if gpx:
            argumentos += ["--gpx", gpx]
        if self.mostrar.get():
            argumentos.append("--mostrar")

        entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                   "PYTHONPATH": str(RAIZ / "src")}
        codigo = "import sys; from tapahuecos.cli import main; sys.exit(main(sys.argv[1:]))"
        self.proceso = subprocess.Popen(
            [python_con_consola(), "-c", codigo, *argumentos], cwd=RAIZ, env=entorno,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._leer_proceso, args=(self.proceso,), daemon=True).start()

        self.registro.configure(state="normal")
        self.registro.delete("1.0", "end")
        self.registro.configure(state="disabled")
        self.detenido = False
        self._escribir(f"Procesando {video.name}…\n")
        self.boton_procesar.configure(state="disabled")
        self.boton_detener.configure(state="normal")
        self.boton_mapa.configure(state="disabled")
        self.boton_carpeta.configure(state="disabled")
        self.barra.grid()
        self.barra.start(12)

    def _leer_proceso(self, proceso: subprocess.Popen) -> None:
        for linea in proceso.stdout:
            self.mensajes.put(linea)
        self.mensajes.put(proceso.wait())

    def _leer_mensajes(self) -> None:
        while not self.mensajes.empty():
            mensaje = self.mensajes.get()
            if isinstance(mensaje, int):
                self._terminado(mensaje)
            else:
                self._escribir(mensaje)
        self.raiz.after(150, self._leer_mensajes)

    def _terminado(self, codigo: int) -> None:
        self.proceso = None
        self.barra.stop()
        self.barra.grid_remove()
        self.boton_procesar.configure(state="normal")
        self.boton_detener.configure(state="disabled")
        bd = self.salida_actual / "danos.db"
        if self.detenido:
            self._escribir("\nDetenido.\n")
            return
        if codigo != 0 or not bd.exists():
            self._escribir(f"\nEl proceso terminó con error (código {codigo}).\n")
            return
        with BaseDatos(bd) as base:
            filas = base.danos()
        self._escribir("\nDaños por clase:\n")
        for clase, tipo, detectados, *_ in filas_por_clase(filas):
            self._escribir(f"  {clase}  {tipo:<24}{detectados:>4}\n")
        self.boton_mapa.configure(state="normal")
        self.boton_carpeta.configure(state="normal")
        if (self.salida_actual / "mapa.html").exists():
            abrir(self.salida_actual / "mapa.html")

    def detener(self) -> None:
        if self.proceso and self.proceso.poll() is None:
            self.detenido = True
            self.proceso.terminate()

    def cerrar(self) -> None:
        self.detener()
        self.raiz.destroy()


def main() -> None:
    raiz = tk.Tk()
    Programa(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
