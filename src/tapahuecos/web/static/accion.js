// Vista previa del comando y ayuda para emparejar video con GPX.
(function () {
  const form = document.querySelector("form.formulario");
  if (!form) return;

  const salida = document.getElementById("vista-previa");
  const accionId = form.dataset.accion;
  let temporizador = null;

  function valores() {
    const datos = {};
    form.querySelectorAll("[name]").forEach((el) => {
      datos[el.name] = el.type === "checkbox" ? (el.checked ? "1" : "") : el.value;
    });
    return datos;
  }

  async function actualizar() {
    try {
      const respuesta = await fetch("/api/comando/" + accionId, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(valores()),
      });
      if (respuesta.ok) salida.textContent = (await respuesta.json()).comando;
    } catch (error) {
      /* Sin red con el servidor: se deja la vista previa como estaba. */
    }
  }

  function programar() {
    clearTimeout(temporizador);
    temporizador = setTimeout(actualizar, 200);
  }

  form.addEventListener("input", programar);
  form.addEventListener("change", programar);

  const boton = form.querySelector("[data-buscar-gpx]");
  if (boton) {
    boton.addEventListener("click", async () => {
      const video = (form.querySelector('[name="video"]') || {}).value || "";
      if (!video) {
        alert("Escriba primero el video.");
        return;
      }
      boton.disabled = true;
      try {
        const respuesta = await fetch("/api/gpx?video=" + encodeURIComponent(video));
        const datos = await respuesta.json();
        if (datos.gpx) {
          form.querySelector('[name="gpx"]').value = datos.gpx;
          programar();
        } else {
          alert("No se encontró un GPX que coincida en hora con ese video.");
        }
      } finally {
        boton.disabled = false;
      }
    });
  }

  form.addEventListener("submit", () => {
    const principal = form.querySelector("button.principal");
    if (principal) {
      principal.disabled = true;
      principal.textContent = "Ejecutando…";
    }
  });

  actualizar();
})();
