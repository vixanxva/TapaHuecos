package com.tapahuecos.gpx

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.graphics.drawable.Icon
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import java.io.File
import java.io.IOException

class GpxRecordingService : Service(), LocationListener {

    companion object {
        const val ACTION_START = "com.tapahuecos.gpx.action.START"
        const val ACTION_STOP = "com.tapahuecos.gpx.action.STOP"

        private const val CHANNEL_ID = "gpx_recording"
        private const val NOTIFICATION_ID = 4_101
        private const val REQUEST_OPEN_APP = 10
        private const val REQUEST_STOP = 11
        private const val LOCATION_INTERVAL_MS = 1_000L
        private const val MAX_ACCURACY_METERS = 100f

        @Volatile
        private var instance: GpxRecordingService? = null

        @Volatile
        private var lastFinished: RecordingSnapshot? = null

        fun snapshot(): RecordingSnapshot? = instance?.currentState ?: lastFinished
    }

    private val handler = Handler(Looper.getMainLooper())
    private val ticker = object : Runnable {
        override fun run() {
            if (!active) return
            currentState = currentState.copy(
                elapsedMillis = SystemClock.elapsedRealtime() - startedElapsedRealtime,
            )
            updateNotification()
            handler.postDelayed(this, LOCATION_INTERVAL_MS)
        }
    }

    private lateinit var locationManager: LocationManager
    private var writer: GpxTrackWriter? = null
    private var trackFile: File? = null
    private var lastLocation: Location? = null
    private var lastPointTimeMillis = 0L
    private var startedAtMillis = 0L
    private var startedElapsedRealtime = 0L
    private var distanceMeters = 0.0
    private var acceptedPoints = 0
    private var active = false
    private var stopping = false

    @Volatile
    private var currentState: RecordingSnapshot = RecordingSnapshot.idle()

    override fun onCreate() {
        super.onCreate()
        instance = this
        locationManager = getSystemService(LocationManager::class.java)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                if (active) {
                    stopRecording()
                } else {
                    stopSelf(startId)
                }
                return START_NOT_STICKY
            }

            ACTION_START -> {
                if (!active && !stopping) {
                    val initial = RecordingSnapshot(phase = RecordingPhase.RECORDING)
                    try {
                        startForegroundCompat(buildNotification(initial))
                    } catch (exception: Exception) {
                        setStartError(getString(R.string.error_could_not_start))
                        stopSelf(startId)
                        return START_NOT_STICKY
                    }
                    startRecording()
                } else {
                    updateNotification()
                }
                return START_NOT_STICKY
            }

            else -> {
                if (!active && !stopping) {
                    stopSelf(startId)
                }
                return START_NOT_STICKY
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startRecording() {
        if (active || stopping) return
        lastFinished = null

        if (!locationManager.allProviders.contains(LocationManager.GPS_PROVIDER)) {
            failStart(getString(R.string.error_gps_unavailable))
            return
        }

        // Solo GPS: la ubicación por red tiene decenas de metros de error y su hora sale
        // del reloj del sistema, no del GNSS; mezclarla ensucia la posición de cada daño.
        if (!locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            failStart(getString(R.string.error_location_disabled))
            return
        }

        val now = System.currentTimeMillis()
        val file = GpxPaths.newLocalFile(this)
        val newWriter = try {
            GpxTrackWriter.create(file, file.nameWithoutExtension, now)
        } catch (exception: Exception) {
            failStart(getString(R.string.error_write, exception.message ?: exception.javaClass.simpleName))
            return
        }

        writer = newWriter
        trackFile = file
        startedAtMillis = now
        startedElapsedRealtime = SystemClock.elapsedRealtime()
        distanceMeters = 0.0
        acceptedPoints = 0
        lastLocation = null
        lastPointTimeMillis = 0L
        stopping = false
        active = true
        currentState = RecordingSnapshot(
            phase = RecordingPhase.RECORDING,
            startedAtMillis = startedAtMillis,
            elapsedMillis = 0L,
            pointCount = 0,
            distanceMeters = 0.0,
            fileName = file.name,
        )

        try {
            requestLocationUpdates()
        } catch (exception: SecurityException) {
            failCurrent(getString(R.string.error_fine_location_required))
            return
        } catch (exception: Exception) {
            failCurrent(getString(R.string.error_generic, exception.message ?: exception.javaClass.simpleName))
            return
        }

        updateNotification()
        handler.post(ticker)
    }

    private fun requestLocationUpdates() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            throw SecurityException("Falta el permiso de ubicación precisa.")
        }

        locationManager.requestLocationUpdates(
            LocationManager.GPS_PROVIDER,
            LOCATION_INTERVAL_MS,
            0f,
            this,
            Looper.getMainLooper(),
        )
    }

    override fun onLocationChanged(location: Location) {
        if (!active) return

        val accuracy = if (location.hasAccuracy()) location.accuracy else null
        if (accuracy != null && accuracy > MAX_ACCURACY_METERS) {
            currentState = currentState.copy(accuracyMeters = accuracy)
            return
        }

        if (!location.latitude.isFinite() ||
            !location.longitude.isFinite() ||
            location.latitude !in -90.0..90.0 ||
            location.longitude !in -180.0..180.0
        ) {
            return
        }

        val timeMillis = if (location.time > 0L) location.time else System.currentTimeMillis()
        if (timeMillis <= lastPointTimeMillis) return

        val point = GpxPoint(
            latitude = location.latitude,
            longitude = location.longitude,
            timeMillis = timeMillis,
            elevationMeters = if (location.hasAltitude()) location.altitude else null,
            accuracyMeters = accuracy,
            speedMetersPerSecond = if (location.hasSpeed()) location.speed else null,
            provider = location.provider,
        )

        val added = try {
            writer?.addPoint(point) ?: false
        } catch (exception: IOException) {
            failCurrent(getString(R.string.error_write, exception.message ?: exception.javaClass.simpleName))
            return
        }
        if (!added) return

        lastLocation?.let { previous ->
            distanceMeters += previous.distanceTo(location).toDouble()
        }
        lastLocation = location
        lastPointTimeMillis = timeMillis
        acceptedPoints += 1

        currentState = currentState.copy(
            elapsedMillis = SystemClock.elapsedRealtime() - startedElapsedRealtime,
            pointCount = acceptedPoints,
            distanceMeters = distanceMeters,
            accuracyMeters = accuracy,
        )
        updateNotification()
    }

    private fun stopRecording() {
        if (!active || stopping) return

        active = false
        stopping = true
        handler.removeCallbacks(ticker)
        removeLocationUpdates()
        writer?.close()
        writer = null

        currentState = currentState.copy(
            phase = RecordingPhase.SAVING,
            elapsedMillis = SystemClock.elapsedRealtime() - startedElapsedRealtime,
            pointCount = acceptedPoints,
            distanceMeters = distanceMeters,
        )
        updateNotification()

        val fileToExport = trackFile
        val baseSnapshot = currentState

        Thread {
            val result = if (fileToExport != null) {
                PublicGpxExporter.export(applicationContext, fileToExport)
            } else {
                PublicGpxExporter.Result.Failure("No se encontró el archivo GPX.")
            }
            handler.post {
                finishRecording(baseSnapshot, result)
            }
        }.apply {
            name = "tapahuecos-gpx-export"
            start()
        }
    }

    private fun finishRecording(
        baseSnapshot: RecordingSnapshot,
        result: PublicGpxExporter.Result,
    ) {
        val finalState = when (result) {
            is PublicGpxExporter.Result.Success -> baseSnapshot.copy(
                phase = RecordingPhase.IDLE,
                exportLabel = result.label,
                exportError = null,
                lastError = null,
            )

            is PublicGpxExporter.Result.Failure -> baseSnapshot.copy(
                phase = RecordingPhase.IDLE,
                exportLabel = null,
                exportError = result.message,
                lastError = null,
            )
        }

        currentState = finalState
        lastFinished = finalState
        stopping = false
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun failStart(message: String) {
        active = false
        stopping = false
        closeWriter()
        deleteEmptyTrack()
        setStartError(message)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun failCurrent(message: String) {
        active = false
        stopping = false
        handler.removeCallbacks(ticker)
        removeLocationUpdates()
        closeWriter()

        val failed = currentState.copy(
            phase = RecordingPhase.ERROR,
            elapsedMillis = if (startedElapsedRealtime > 0L) {
                SystemClock.elapsedRealtime() - startedElapsedRealtime
            } else {
                currentState.elapsedMillis
            },
            pointCount = acceptedPoints,
            distanceMeters = distanceMeters,
            lastError = message,
        )
        currentState = failed
        lastFinished = failed
        if (acceptedPoints == 0) deleteEmptyTrack()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun setStartError(message: String) {
        val failed = RecordingSnapshot(
            phase = RecordingPhase.ERROR,
            lastError = message,
        )
        currentState = failed
        lastFinished = failed
    }

    private fun closeWriter() {
        runCatching { writer?.close() }
        writer = null
    }

    private fun deleteEmptyTrack() {
        if (acceptedPoints == 0) {
            runCatching { trackFile?.delete() }
            trackFile = null
        }
    }

    private fun removeLocationUpdates() {
        runCatching { locationManager.removeUpdates(this) }
    }

    private fun startForegroundCompat(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun updateNotification() {
        if (!active && currentState.phase != RecordingPhase.SAVING) return
        runCatching {
            getSystemService(NotificationManager::class.java)
                .notify(NOTIFICATION_ID, buildNotification(currentState))
        }
    }

    private fun buildNotification(snapshot: RecordingSnapshot): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPendingIntent = PendingIntent.getActivity(
            this,
            REQUEST_OPEN_APP,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopPendingIntent = PendingIntent.getService(
            this,
            REQUEST_STOP,
            Intent(this, GpxRecordingService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val contentText = when {
            snapshot.phase == RecordingPhase.SAVING -> getString(R.string.notification_saving)
            snapshot.pointCount == 0 -> getString(R.string.notification_searching)
            else -> resources.getQuantityString(
                R.plurals.notification_text,
                snapshot.pointCount,
                Formatters.duration(snapshot.elapsedMillis),
                snapshot.pointCount,
                Formatters.distance(snapshot.distanceMeters),
            )
        }

        val builder = Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_gpx)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(contentText)
            .setContentIntent(openPendingIntent)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setColor(getColor(R.color.accent))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setVisibility(Notification.VISIBILITY_PRIVATE)

        snapshot.fileName?.let { fileName ->
            builder.setSubText(fileName)
        }

        if (snapshot.phase == RecordingPhase.RECORDING) {
            builder.addAction(
                Notification.Action.Builder(
                    Icon.createWithResource(this, R.drawable.ic_stop),
                    getString(R.string.notification_stop),
                    stopPendingIntent,
                ).build(),
            )
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            builder.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
        }

        return builder.build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.notification_channel_description)
            setShowBadge(false)
            enableVibration(false)
            setSound(null, null)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (active) {
            removeLocationUpdates()
            closeWriter()
            val interrupted = currentState.copy(
                phase = RecordingPhase.ERROR,
                lastError = getString(
                    R.string.error_generic,
                    "el servicio de grabación fue detenido por el sistema",
                ),
            )
            currentState = interrupted
            lastFinished = interrupted
        } else {
            closeWriter()
        }
        if (instance === this) instance = null
        super.onDestroy()
    }
}
