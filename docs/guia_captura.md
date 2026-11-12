# Guía de captura: video + GPX

## Equipo

- Celular o cámara de acción para el video, en un soporte firme (en el parabrisas, o en el manubrio si es moto).
- Celular con una app que grabe GPX; en Android, por ejemplo, **GPS Logger** (BasicAirData o Mendhak). Puede ser el mismo celular que graba el video, si la app sigue funcionando en segundo plano.

## Configuración

| Parámetro | Valor recomendado |
|---|---|
| Resolución del video | 1080p (720p como mínimo) |
| Fotogramas por segundo | 30 |
| Estabilización | Activada |
| Intervalo del GPS | 1 s |
| Formato del recorrido | GPX |
| Hora del celular | Automática (de la red) |

## Antes de grabar

1. Verificar que la hora del celular está en automático. Así la cámara y el GPS comparten el mismo reloj.
2. Abrir la app GPS y esperar a que la precisión sea menor a 10 m.
3. Montar la cámara apuntando a la vía, con el horizonte en el tercio superior de la imagen. **No moverla durante la campaña**: la calibración de área depende de esa posición.
4. Si es el primer día con ese montaje, grabar el video de calibración (ver más abajo).

## Durante el recorrido

- Iniciar primero el GPX y después el video. Detener primero el video y después el GPX. Así el recorrido GPS cubre todo el video.
- Mantener una velocidad baja y constante (menos de 30 km/h).
- Preferir días con buena luz; evitar el amanecer, el atardecer y la lluvia fuerte.
- Anotar el nombre de cada calle y la hora de cada recorrido.

## Nombres de archivo

No hay que renombrar los videos: el programa toma la hora de inicio del nombre que pone la cámara (`VID_20261029_143015.mp4`, `PXL_20261029_143015123.mp4`, `20261029_143015.mp4`). Si la cámara usa otro formato (`IMG_1234.MOV`, `GX010023.MP4`) o el video pasó por WhatsApp (`VID-20261029-WA0001.mp4`, sin hora), hay que indicar la hora con `--inicio 2026-10-29T14:30:15`.

Organización sugerida:

```
datos/videos/VID_20261029_143015.mp4
datos/gpx/20261029-1430.gpx
```

## Video de calibración

Con el vehículo detenido y la cámara en su posición definitiva, se graban unos segundos de un tramo de vía con un rectángulo de medidas conocidas: marcas viales, o cuatro conos o tapas colocados con cinta métrica (por ejemplo, 3 m de ancho × 5 m de largo). Después:

```bash
python scripts/calibrar_homografia.py --video datos/videos/calibracion.mp4 --segundo 2 --ancho 3 --largo 5
```

## Si el video sale girado

Lo normal es que el programa enderece el video solo, con la orientación que guarda el celular. Si aun así sale de lado o de cabeza (por ejemplo, porque se grabó en vertical o la cámara está montada al revés), poner en `config.yaml` el giro que falta, en sentido horario: `rotacion: 90`, `180` o `270`. Usar el mismo valor al calibrar: `calibrar_homografia.py ... --rotacion 90`.

## Videos en vertical

Si el video se grabó en vertical, la vía queda solo en la parte de abajo. Para que el modelo se concentre en ella, procesar solo esa franja: `region: [0, 0.45, 1, 1]` en `config.yaml`, o `--region 0,0.45,1,1` en `tapahuecos procesar`. Revisar en el video anotado (el rectángulo gris) que la franja cubra toda la vía.

## Si los puntos salen corridos en el mapa

- **Todos desplazados a lo largo de la calle:** el reloj de la cámara y el del GPS no coinciden. Ajustar `desfase_gps_s` en `config.yaml` (en segundos, positivo o negativo).
- **El programa avisa que el video no coincide con el GPX:** revisar `utc_offset_horas` o indicar `--inicio`.
