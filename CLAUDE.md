# Instrucciones para Claude

Detector de daños en las vías (YOLO + OpenCV) del equipo. El código, los comentarios, los commits, los Pull Requests y la documentación van en español. El detalle del proceso está en [CONTRIBUTING.md](CONTRIBUTING.md); aquí va lo que una sesión de Claude tiene que saber antes de tocar git o GitHub.

## Ramas: solo `main` y `develop`

Desde el 2026-11-05 (PR #50) **no se crean ramas por tarea** (`feature/…`, `fix/…`, `docs/…` quedaron en desuso; las ramas viejas se borraron).

- **Se trabaja en `develop`.** Antes de empezar: `git switch develop && git pull`. Los commits se suben directo a `develop`, sin Pull Request.
- **`main` solo recibe lo que ya sirve**, por Pull Request desde `develop`. Lo que cause duda (falta validarlo, el resultado no convence, está a medias) se queda en `develop`.
- **Si en `develop` hay algo dudoso** mezclado con lo que sirve, se arma la rama temporal `promocion` desde `origin/main` con `git cherry-pick` de los commits listos, y el Pull Request sale de ahí. Es la única rama extra permitida y se borra sola al fusionar.
- **Después de cada fusión en `main`**, sincronizar `develop`:
  ```bash
  git switch develop && git pull
  git merge --no-edit origin/main
  git push
  ```
  Usar siempre `--no-edit`: sin él Git abre Vim y, si se cierra la ventana, el merge queda a medias. Si eso pasa (`.git/MERGE_HEAD` existe), terminarlo con `git commit -m "Sincronizar develop con main"` y borrar `.git/.MERGE_MSG.swp`. No usar `git commit --no-edit` en ese caso: deja en el título las líneas de comentario de la plantilla (pasó en el commit `3c84095`).

## Commits

- Un commit, una tarea, con el número de la issue: `Ajusta el umbral de Otsu para grietas (#12)`. No mezclar dos issues en un commit: impide pasar a `main` solo una de ellas.
- **Nunca** `Closes`, `Fixes` ni `Resolves` en un commit: al llegar a `main` cerrarían la issue aunque no cumpla su criterio.
- Antes de subir: `ruff check src scripts tests` y `pytest`. `develop` es compartida: nada que rompa la CI y nunca `push --force` (está bloqueado).

## Pull Requests a `main` y cierre de issues

- Una línea por issue en "Qué cambia". `Closes #N` **solo** si se cumple todo el "Terminado cuando" de la issue, comparado casilla por casilla; si falta algo, `Refs #N` y decir qué falta.
- Antes de proponer el cierre de una issue, leer sus comentarios (`gh issue view N --comments`): las reabiertas tienen condiciones extra en un comentario "Reabierta: … Falta para cerrarla:".
- Si un criterio no se cumple, preguntar al responsable; puede aceptarlo, y entonces la issue se cierra a mano con un comentario que lo diga. Nunca presentar un criterio incumplido como cumplido.
- Se fusiona con *Squash and merge* (la única opción habilitada).

## Protecciones en GitHub

| Rama | Protección |
|---|---|
| `main` | CI en verde (`pruebas` 3.10, 3.11 y 3.12) y aprobación del code owner (`@vixanxva`, ver `.github/CODEOWNERS`). |
| `develop` | Sin revisión ni CI obligatoria, pero no se puede borrar ni hacer `push --force`. |

El repositorio borra la rama al fusionar un Pull Request; la protección evita que se borre `develop`.

Como el code owner no puede aprobar sus propios Pull Requests, fusionarlos exige `gh pr merge N --squash --admin`. **Claude no ejecuta ese comando**: el modo automático lo bloquea por saltarse la revisión. Claude deja el Pull Request listo con la CI en verde, y el responsable lo fusiona o lo revisa otro integrante. Lo mismo vale para borrar ramas locales con `git branch -D`: se le da el comando al usuario.

## Reglas del proyecto

- Los parámetros ajustables van en `config.yaml`, no en el código.
- No se versionan videos, GPX, datasets ni pesos `.pt`; van en Google Drive o Roboflow.
- Los cambios de comportamiento llevan prueba en `tests/`, sin requerir YOLO ni GPU.
- Los contratos de [docs/contratos.md](docs/contratos.md) no se cambian de paso; las dependencias de `pyproject.toml` no se tocan sin acordarlo.
