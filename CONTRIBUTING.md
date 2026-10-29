# Cómo contribuir

## Flujo de trabajo

1. Tomar una issue del tablero (o crearla con la plantilla **Tarea**) y asignársela.
2. Crear una rama desde `main` actualizado:
   ```bash
   git switch main && git pull
   git switch -c feature/12-segmentacion-grietas   # <tipo>/<n.º de issue>-<descripción>
   ```
   Tipos: `feature/`, `fix/`, `docs/`, `data/`, `exp/` (experimentos de entrenamiento).
3. Hacer commits pequeños, con mensajes en imperativo: `Ajusta el umbral de Otsu para grietas`.
4. Antes de abrir el Pull Request:
   ```bash
   ruff check src scripts tests
   pytest
   ```
5. Abrir el Pull Request hacia `main`, completar la plantilla y enlazar la issue (`Closes #12`).
6. Al menos **un integrante distinto** al autor revisa y aprueba. La CI debe pasar.
7. Fusionar con *Squash and merge* y borrar la rama.

## Reglas

- `main` siempre debe funcionar. Nada se sube directo a `main`.
- No se versionan videos, GPX, datasets ni pesos (`.pt`): se comparten por Google Drive o Roboflow y se enlazan en la issue o en `modelos/README.md`.
- Los cambios de comportamiento llevan su prueba en `tests/`. Las pruebas no deben requerir YOLO ni GPU (ver `tests/test_pipeline.py`, que usa un detector simulado).
- Los parámetros ajustables van en `config.yaml`, no fijos en el código.
- El código, los comentarios y la documentación se escriben en español.

## Entorno

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS
pip install -e ".[yolo,dev]"
```
