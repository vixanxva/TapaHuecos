## Qué cambia


<!--
Este PR pasa a main lo que ya sirve de develop (directo desde develop o desde la rama temporal promocion).
Lo que cause duda se queda en develop. Una línea por issue:
Closes #N: solo si este PR cumple TODO el "Terminado cuando" de la issue. Al fusionar, GitHub la cierra.
Refs #N: si queda algo pendiente (validación con datos reales, prueba en Colab, etc.). La issue sigue abierta.
-->
Closes #

## Cómo se probó

- [ ] `ruff check src scripts tests`
- [ ] `pytest`
- [ ] Probado con un video real (si aplica): resultado / captura

## Lista de revisión

- [ ] Los parámetros nuevos están en `config.yaml`
- [ ] No se subieron videos, GPX, datasets ni pesos `.pt`
- [ ] La documentación (`README.md` / `docs/`) está actualizada
