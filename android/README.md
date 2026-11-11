# TapaHuecos GPX (app Android)

App compañera del pipeline. Graba el recorrido GPS en **GPX 1.1** mientras se graba
video con la cámara normal del teléfono. No graba video ni procesa daños: solo produce
el archivo que después se pasa a `tapahuecos procesar`.

## Qué hace

- Graba **un punto por segundo** con `LocationManager` y `GPS_PROVIDER`.
- Funciona como **servicio en primer plano** con notificación persistente: sigue
  grabando con la pantalla apagada o la app en segundo plano.
- Descarta puntos sin coordenada o con precisión peor que 100 m y calcula distancia y
  velocidad medias en pantalla.
- Escribe el GPX de forma **incremental**: después de cada punto el XML ya está
  cerrado y es válido, aunque Android mate el proceso o se agote la batería.
- Guarda una copia privada y exporta otra a `Documents/TapaHuecos` (en Android 10 o
  superior usa MediaStore, sin pedir permiso de almacenamiento; en Android 8 y 9 usa
  `WRITE_EXTERNAL_STORAGE`). Si `Documents` falla, intenta `Downloads/TapaHuecos`.
- Permite **compartir** el GPX con otra app mediante `FileProvider`.
- Muestra las últimas grabaciones y sus métricas.

## Requisitos

- Android 8.0 o superior (API 26).
- Permiso de **ubicación precisa** y, en Android 13 o superior, permiso de
  **notificaciones**.
- GPS activado. La app no graba si el proveedor GPS está apagado.
- Para compilar: JDK 17 y Android SDK con `compileSdk 37`. El proyecto usa AGP 9.4.0,
  Gradle 9.6.0 y el wrapper incluido.

## Uso en campo

1. Instalar la APK y abrir la app.
2. Conceder ubicación precisa y notificaciones.
3. Pulsar **Iniciar**. La notificación persistente confirma que el servicio está
   activo.
4. **Iniciar primero el GPX y después el video** con la cámara normal.
5. Al terminar, **detener primero el video y después el GPX**.
6. Exportar o compartir el GPX. La copia privada queda en
   `Android/data/com.tapahuecos.gpx/files/Documents/TapaHuecos/` y la pública en
   `Documents/TapaHuecos/`.
7. Copiar el GPX a `datos/gpx/` del computador y procesarlo con su video.

> En algunos fabricantes (Xiaomi, Huawei, Samsung, etc.) hay que permitir que la app
> siga funcionando en segundo plano o desactivar la optimización de batería. Sin eso,
> el sistema puede detener el servicio aunque la notificación siga visible.

## Compilar y probar

```bash
cd android
./gradlew assembleDebug testDebugUnitTest lintDebug
```

- APK: `app/build/outputs/apk/debug/app-debug.apk`.
- Instalar en un dispositivo conectado por ADB:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

También se puede abrir `android/` con Android Studio y ejecutar la configuración
`app`.

## Estructura

| Archivo | Función |
|---|---|
| `MainActivity.kt` | Pantalla de control, permisos, métricas y lista de grabaciones |
| `GpxRecordingService.kt` | Servicio en primer plano, GPS y notificación persistente |
| `GpxTrackWriter.kt` | Escritor GPX 1.1 incremental y válido tras cada punto |
| `GpxPaths.kt` | Rutas de la copia privada y nombres de sesión |
| `PublicGpxExporter.kt` | Exportación a `Documents/TapaHuecos` con MediaStore o almacenamiento clásico |
| `GpxPoint.kt`, `RecordingSnapshot.kt`, `Formatters.kt` | Modelo y formato de métricas |
| `app/src/test/.../GpxTrackWriterTest.kt` | Pruebas del XML, puntos inválidos y cierre del archivo |

## Limitaciones y estado

- **No se ha probado todavía en un teléfono físico.** El build, las pruebas unitarias
  y Lint pasan; falta grabar con la pantalla apagada y verificar el GPX en campo.
- El GPS del teléfono puede tardar unos segundos en fijar la primera posición. La app
  muestra la precisión y no escribe puntos con precisión peor que 100 m.
- La app no controla la cámara ni sincroniza relojes: la sincronización se hace por la
  hora de inicio del nombre del video y la hora UTC del GPX, como se explica en
  [docs/guia_captura.md](../docs/guia_captura.md).
