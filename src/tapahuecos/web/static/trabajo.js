// Sigue el trabajo en curso: pide las líneas nuevas cada segundo hasta que termina.
(function () {
  const pre = document.getElementById("salida");
  const estado = document.getElementById("estado");
  if (!pre || !estado) return;

  const id = estado.dataset.id;
  let desde = parseInt(pre.dataset.desde || "0", 10);
  let terminado = false;

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
      const fin =
        datos.estado === "terminado"
          ? "Terminado"
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
