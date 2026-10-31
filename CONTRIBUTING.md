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
5. Abrir el Pull Request hacia `main`, completar la plantilla y enlazar la issue:
   - `Closes #12` solo si el PR cumple todo el "Terminado cuando" de la issue. Al fusionarlo, GitHub la cierra.
   - `Refs #12` si queda algo pendiente, como la validación con datos reales. La issue sigue abierta y se cierra a mano cuando se cumple el criterio, con las casillas marcadas y la evidencia (captura, métrica o enlace a Drive).
6. Al menos **un integrante distinto** al autor revisa y aprueba. La CI debe pasar.
7. Fusionar con *Squash and merge* y borrar la rama.

## Reglas

- `main` siempre debe funcionar. Nada se sube directo a `main`.
- No se versionan videos, GPX, datasets ni pesos (`.pt`): se comparten por Google Drive o Roboflow y se enlazan en la issue o en `modelos/README.md`.
- Los cambios de comportamiento llevan su prueba en `tests/`. Las pruebas no deben requerir YOLO ni GPU (ver `tests/test_pipeline.py`, que usa un detector simulado).
- Los parámetros ajustables van en `config.yaml`, no fijos en el código.
- El código, los comentarios y la documentación se escriben en español.

### Trabajo en paralelo

- **Una tarea, sus archivos.** Cada issue dice qué archivos toca; un Pull Request no modifica archivos de otra tarea. Si hace falta, se abre otra issue.
- **Los contratos no se cambian de paso.** Las firmas, tipos y columnas de [docs/contratos.md](docs/contratos.md) son lo que permite trabajar cada módulo por separado. Cambiarlos va en un Pull Request aparte, que actualiza ese documento y se avisa al equipo antes de fusionarlo.
- **Las dependencias no se tocan sin acordarlo.** Se declaran una sola vez en `pyproject.toml` (`requirements.txt` solo apunta allí). Agregar o cambiar una se discute en la issue primero.
- **Cada tarea trae sus datos de prueba.** Si un módulo necesita un video, GPX, imagen o CSV de ejemplo, se genera en [tests/fixtures/generar.py](tests/fixtures/generar.py), no se sube el archivo.
- **CI en verde para fusionar.** Ningún Pull Request se fusiona con la CI fallando.

## Entorno

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS
pip install -e ".[yolo,dev]"
```
