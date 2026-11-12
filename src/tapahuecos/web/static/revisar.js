// Marca cada recorte como real o falso positivo y actualiza los contadores.
(function () {
  const galeria = document.getElementById("galeria");
  if (!galeria) return;

  const db = new URLSearchParams(location.search).get("db") || "salidas/danos.db";
  const revisados = document.getElementById("revisados");
  const reales = document.getElementById("reales");
  const pendientes = document.getElementById("pendientes");
  const precision = document.getElementById("precision");

  galeria.addEventListener("click", async (evento) => {
    const boton = evento.target.closest("button[data-real]");
    if (!boton) return;
    const figura = boton.closest(".recorte");
    const real = boton.dataset.real === "1";

    figura.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      const respuesta = await fetch("/api/revisar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          db: db,
          id: parseInt(figura.dataset.id, 10),
          real: real,
        }),
      });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.error || "fallo");

      figura.classList.add(real ? "marcado-real" : "marcado-falso");
      const total = datos.revisados + datos.pendientes;
      if (revisados) revisados.textContent = datos.revisados;
      if (reales) reales.textContent = datos.reales;
      if (pendientes) pendientes.textContent = datos.pendientes;
      if (precision) {
        precision.textContent = datos.revisados ? (datos.reales / datos.revisados).toFixed(3) : "—";
      }
      figura.dataset.total = total;
    } catch (error) {
      figura.querySelectorAll("button").forEach((b) => (b.disabled = false));
      alert("No se pudo guardar la revisión: " + error.message);
    }
  });
})();
