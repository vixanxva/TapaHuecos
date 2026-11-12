// Sigue el trabajo en curso: pide las líneas nuevas cada segundo hasta que termina.
(function () {
  const pre = document.getElementById("salida");
  const estado = document.getElementById("estado");
  if (!pre || !estado) return;

  const id = estado.dataset.id;
  const cancelar = document.getElementById("cancelar");
  let desde = parseInt(pre.dataset.desde || "0", 10);
  let terminado = false;

  if (cancelar) {
    cancelar.addEventListener("click", async function () {
      if (!window.confirm("¿Detener este trabajo? Lo que ya escribió se conserva.")) return;
      cancelar.disabled = true;
      cancelar.textContent = "Cancelando…";
      try {
        await fetch("/api/trabajo/" + id + "/cancelar", { method: "POST" });
      } catch (error) {
        cancelar.disabled = false;
        cancelar.textContent = "Cancelar";
      }
    });
  }

  function pintar(datos) {
    if (datos.lineas && datos.lineas.length) {
      pre.textContent += datos.lineas.join("\n") + "\n";
      desde = datos.total;
      pre.scrollTop = pre.scrollHeight;
    }
    if (datos.estado === "en_curso") {
      estado.textContent = "En curso… " + datos.segundos + " s";
      estado.className = "estado en-curso";
    } else {
      terminado = true;
      if (cancelar) cancelar.hidden = true;
      const fin =
        datos.estado === "terminado"
          ? "Terminado"
          : datos.estado === "cancelado"
            ? "Cancelado"
            : "Terminó con error (código " + datos.codigo + ")";
      estado.textContent = fin + " en " + datos.segundos + " s";
      estado.className = "estado " + datos.estado;
    }
  }

  async function consultar() {
    try {
      const respuesta = await fetch("/api/trabajo/" + id + "?desde=" + desde);
      if (respuesta.ok) pintar(await respuesta.json());
    } catch (error) {
      /* Red caída: se reintenta en el siguiente ciclo. */
    }
    if (!terminado) setTimeout(consultar, 1000);
  }

  consultar();
})();
