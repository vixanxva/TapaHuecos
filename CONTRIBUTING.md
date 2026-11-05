# Cómo contribuir

## Ramas

Hay solo dos ramas permanentes y **no se crean ramas por tarea**:

| Rama | Qué tiene |
|---|---|
| `main` | Lo que ya sirve: probado y que cumple su "Terminado cuando". Siempre funciona. Solo recibe cambios por Pull Request desde `develop`. |
| `develop` | Donde se trabaja. Todo se sube aquí, y aquí se queda lo que todavía causa duda (falta validarlo, no convence el resultado, está a medias). |

## Flujo de trabajo

1. Tomar una issue del tablero (o crearla con la plantilla **Tarea**) y asignársela.
2. Trabajar sobre `develop` actualizado:
   ```bash
   git switch develop && git pull
   ```
3. Hacer commits pequeños, con mensajes en imperativo y el número de la issue: `Ajusta el umbral de Otsu para grietas (#12)`.
   - **Un commit, una tarea.** No mezclar en un commit cambios de dos issues: así lo que sirve se puede pasar a `main` sin arrastrar lo que causa duda.
   - En los commits nunca se escribe `Closes`, `Fixes` ni `Resolves`: cerrarían la issue al llegar a `main` aunque no cumpla el criterio. Basta con `(#12)`.
4. Antes de subir:
   ```bash
   ruff check src scripts tests
   pytest
   git pull --rebase && git push
   ```
   `develop` es compartida: no se sube nada que rompa la CI ni se hace `push --force`.
5. Cuando algo de `develop` sirve, se pasa a `main` (ver [Pasar a main](#pasar-a-main)). Lo que cause duda se queda en `develop` hasta resolverse.

## Pasar a main

Se abre un Pull Request hacia `main` con la plantilla. En "Qué cambia" va una línea por issue:

- `Closes #12` solo si cumple todo el "Terminado cuando" de la issue. Al fusionarlo, GitHub la cierra.
- `Refs #12` si queda algo pendiente, como la validación con datos reales. La issue sigue abierta y se cierra a mano cuando se cumple el criterio, con las casillas marcadas y la evidencia (captura, métrica o enlace a Drive).

**Si todo lo de `develop` sirve**, el Pull Request va directo de `develop` a `main`:

```bash
gh pr create --base main --head develop
```

**Si en `develop` hay algo que causa duda**, solo se lleva lo que sirve. Se arma una rama temporal `promocion` desde `main` con esos commits (es la única rama extra que se crea, y se borra sola al fusionar):

```bash
git fetch origin
git switch -c promocion origin/main
git log --oneline origin/main..origin/develop   # elegir los commits que sirven
git cherry-pick <commit> <commit> ...
git push -u origin promocion
gh pr create --base main --head promocion
```

En los dos casos:

1. Al menos **un integrante distinto** al autor revisa y aprueba. La CI debe pasar.
2. Se fusiona con *Squash and merge*.
3. Después se pone `develop` al día con `main`, para que el próximo Pull Request muestre solo lo nuevo:
   ```bash
   git switch develop && git pull
   git merge --no-edit origin/main
   git push
   ```
   Con `--no-edit` Git no abre el editor (Vim). Si se abre y se cierra la ventana, el merge queda a medias: se termina con `git commit -m "Sincronizar develop con main"`.

## Reglas

- `main` siempre debe funcionar. Nada se sube directo a `main`.
- `develop` está protegida contra borrado y `push --force`.
- No se versionan videos, GPX, datasets ni pesos (`.pt`): se comparten por Google Drive o Roboflow y se enlazan en la issue o en `modelos/README.md`.
- Los cambios de comportamiento llevan su prueba en `tests/`. Las pruebas no deben requerir YOLO ni GPU (ver `tests/test_pipeline.py`, que usa un detector simulado).
- Los parámetros ajustables van en `config.yaml`, no fijos en el código.
- El código, los comentarios y la documentación se escriben en español.

### Trabajo en paralelo

- **Una tarea, sus archivos.** Cada issue dice qué archivos toca; un commit no modifica archivos de otra tarea. Si hace falta, se abre otra issue.
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
