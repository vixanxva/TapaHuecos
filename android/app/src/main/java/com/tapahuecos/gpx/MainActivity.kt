package com.tapahuecos.gpx

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.net.toUri
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : Activity() {

    companion object {
        private const val REQUEST_PERMISSIONS = 100
        private const val START_TIMEOUT_MS = 5_000L
    }

    private lateinit var scrollRoot: ScrollView
    private lateinit var tvStatus: TextView
    private lateinit var tvStateTitle: TextView
    private lateinit var tvStateHint: TextView
    private lateinit var tvDuration: TextView
    private lateinit var tvPoints: TextView
    private lateinit var tvDistance: TextView
    private lateinit var tvAccuracy: TextView
    private lateinit var tvExport: TextView
    private lateinit var tvRecentEmpty: TextView
    private lateinit var llRecent: LinearLayout
    private lateinit var btnStart: Button
    private lateinit var btnStop: Button

    private val pollHandler = Handler(Looper.getMainLooper())
    private val pollRunnable = object : Runnable {
        override fun run() {
            refreshState()
            pollHandler.postDelayed(this, 1_000L)
        }
    }

    private var pendingStartAfterPermission = false
    private var startRequested = false
    private var startRequestedAt = 0L
    private var lastRenderedPhase: RecordingPhase? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        bindViews()
        applyWindowInsets()

        btnStart.setOnClickListener { requestPermissionsAndStart() }
        btnStop.setOnClickListener { stopRecording() }
        findViewById<TextView>(R.id.tv_battery_settings).setOnClickListener { openBatterySettings() }

        refreshRecent()
        render(GpxRecordingService.snapshot() ?: RecordingSnapshot.idle())
    }

    override fun onResume() {
        super.onResume()
        pollHandler.removeCallbacks(pollRunnable)
        pollHandler.post(pollRunnable)
        refreshRecent()
    }

    override fun onPause() {
        pollHandler.removeCallbacks(pollRunnable)
        super.onPause()
    }

    override fun onDestroy() {
        pollHandler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun bindViews() {
        scrollRoot = findViewById(R.id.scroll_root)
        tvStatus = findViewById(R.id.tv_status)
        tvStateTitle = findViewById(R.id.tv_state_title)
        tvStateHint = findViewById(R.id.tv_state_hint)
        tvDuration = findViewById(R.id.tv_duration)
        tvPoints = findViewById(R.id.tv_points)
        tvDistance = findViewById(R.id.tv_distance)
        tvAccuracy = findViewById(R.id.tv_accuracy)
        tvExport = findViewById(R.id.tv_export)
        tvRecentEmpty = findViewById(R.id.tv_recent_empty)
        llRecent = findViewById(R.id.ll_recent)
        btnStart = findViewById(R.id.btn_start)
        btnStop = findViewById(R.id.btn_stop)
    }

    private fun applyWindowInsets() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return

        window.setDecorFitsSystemWindows(false)
        ViewCompat.setOnApplyWindowInsetsListener(scrollRoot) { view, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout(),
            )
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
    }

    private fun requestPermissionsAndStart() {
        if (isBusy()) return

        val needed = mutableListOf<String>()
        if (!hasPermission(Manifest.permission.ACCESS_FINE_LOCATION)) {
            needed += Manifest.permission.ACCESS_FINE_LOCATION
            needed += Manifest.permission.ACCESS_COARSE_LOCATION
        }
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P &&
            !hasPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        ) {
            needed += Manifest.permission.WRITE_EXTERNAL_STORAGE
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            !hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        ) {
            needed += Manifest.permission.POST_NOTIFICATIONS
        }

        if (needed.isEmpty()) {
            startIfLocationEnabled()
        } else {
            pendingStartAfterPermission = true
            requestPermissions(needed.toTypedArray(), REQUEST_PERMISSIONS)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_PERMISSIONS) return

        if (!hasPermission(Manifest.permission.ACCESS_FINE_LOCATION)) {
            pendingStartAfterPermission = false
            showLocationPermissionDialog()
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            !hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        ) {
            Toast.makeText(this, R.string.notification_permission_missing, Toast.LENGTH_LONG).show()
        }

        if (pendingStartAfterPermission) {
            pendingStartAfterPermission = false
            startIfLocationEnabled()
        }
    }

    private fun startIfLocationEnabled() {
        if (isBusy()) return

        val locationManager = getSystemService(LocationManager::class.java)
        val enabled = runCatching {
            locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
                locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        }.getOrDefault(false)

        if (!enabled) {
            showLocationDisabledDialog()
            return
        }

        startRequested = true
        startRequestedAt = SystemClock.elapsedRealtime()
        btnStart.isEnabled = false
        btnStop.isEnabled = false

        try {
            val intent = Intent(this, GpxRecordingService::class.java)
                .setAction(GpxRecordingService.ACTION_START)
            startForegroundService(intent)
        } catch (exception: Exception) {
            startRequested = false
            render(GpxRecordingService.snapshot() ?: RecordingSnapshot(phase = RecordingPhase.ERROR))
            Toast.makeText(
                this,
                getString(R.string.error_could_not_start),
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    private fun stopRecording() {
        btnStop.isEnabled = false
        try {
            startService(
                Intent(this, GpxRecordingService::class.java)
                    .setAction(GpxRecordingService.ACTION_STOP),
            )
        } catch (exception: Exception) {
            Toast.makeText(
                this,
                getString(R.string.error_generic, exception.message ?: exception.javaClass.simpleName),
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    private fun refreshState() {
        if (startRequested &&
            SystemClock.elapsedRealtime() - startRequestedAt > START_TIMEOUT_MS
        ) {
            startRequested = false
        }

        val snapshot = GpxRecordingService.snapshot() ?: RecordingSnapshot.idle()
        if (snapshot.phase == RecordingPhase.RECORDING ||
            snapshot.phase == RecordingPhase.SAVING ||
            snapshot.phase == RecordingPhase.ERROR
        ) {
            startRequested = false
        }

        val previousPhase = lastRenderedPhase
        render(snapshot)
        lastRenderedPhase = snapshot.phase
        if (previousPhase == RecordingPhase.SAVING && snapshot.phase == RecordingPhase.IDLE) {
            refreshRecent()
        }
    }

    private fun render(snapshot: RecordingSnapshot) {
        val busy = snapshot.phase == RecordingPhase.RECORDING ||
            snapshot.phase == RecordingPhase.SAVING
        btnStart.isEnabled = !busy && !startRequested
        btnStop.isEnabled = snapshot.phase == RecordingPhase.RECORDING

        when (snapshot.phase) {
            RecordingPhase.RECORDING -> {
                setStatus(R.string.status_recording, R.drawable.bg_pill_recording, R.color.accent)
                tvStateTitle.setText(R.string.state_recording_title)
                tvStateHint.setText(R.string.state_recording_hint)
            }

            RecordingPhase.SAVING -> {
                setStatus(R.string.status_saving, R.drawable.bg_pill_saving, R.color.warning)
                tvStateTitle.setText(R.string.state_saving_title)
                tvStateHint.setText(R.string.state_saving_hint)
            }

            RecordingPhase.ERROR -> {
                setStatus(R.string.status_error, R.drawable.bg_pill_error, R.color.danger)
                tvStateTitle.setText(R.string.state_error_title)
                tvStateHint.text = snapshot.lastError ?: getString(R.string.state_error_hint)
            }

            RecordingPhase.IDLE -> {
                setStatus(R.string.status_ready, R.drawable.bg_pill_idle, R.color.accent)
                tvStateTitle.setText(R.string.state_idle_title)
                tvStateHint.setText(R.string.state_idle_hint)
            }
        }

        val hasSession = snapshot.phase != RecordingPhase.IDLE ||
            snapshot.pointCount > 0 ||
            snapshot.startedAtMillis > 0L
        tvDuration.text = if (hasSession) {
            Formatters.duration(snapshot.elapsedMillis)
        } else {
            getString(R.string.value_empty)
        }
        tvPoints.text = if (hasSession) snapshot.pointCount.toString() else getString(R.string.value_empty)
        tvDistance.text = if (hasSession) {
            Formatters.distance(snapshot.distanceMeters)
        } else {
            getString(R.string.value_empty)
        }
        tvAccuracy.text = when {
            snapshot.phase == RecordingPhase.RECORDING && snapshot.accuracyMeters == null ->
                getString(R.string.value_no_fix)

            snapshot.accuracyMeters != null -> Formatters.accuracy(snapshot.accuracyMeters)
            else -> getString(R.string.value_empty)
        }

        val exportText = when {
            snapshot.exportLabel != null ->
                getString(R.string.export_ok) + "\n" + snapshot.exportLabel

            snapshot.exportError != null ->
                getString(R.string.error_public_export) + "\n" + snapshot.exportError

            snapshot.phase == RecordingPhase.ERROR && snapshot.lastError != null ->
                snapshot.lastError

            else -> null
        }
        tvExport.text = exportText
        tvExport.visibility = if (exportText.isNullOrBlank()) View.GONE else View.VISIBLE
    }

    private fun setStatus(textRes: Int, backgroundRes: Int, colorRes: Int) {
        tvStatus.setText(textRes)
        tvStatus.setBackgroundResource(backgroundRes)
        tvStatus.setTextColor(getColor(colorRes))
    }

    private fun isBusy(): Boolean {
        val phase = GpxRecordingService.snapshot()?.phase
        return startRequested ||
            phase == RecordingPhase.RECORDING ||
            phase == RecordingPhase.SAVING
    }

    private fun hasPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
    }

    private fun showLocationPermissionDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.dialog_location_title)
            .setMessage(R.string.dialog_location_message)
            .setPositiveButton(R.string.dialog_open_settings) { _, _ -> openAppSettings() }
            .setNegativeButton(R.string.dialog_cancel, null)
            .show()
    }

    private fun showLocationDisabledDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.dialog_gps_title)
            .setMessage(R.string.dialog_gps_message)
            .setPositiveButton(R.string.dialog_gps_settings) { _, _ -> openLocationSettings() }
            .setNegativeButton(R.string.dialog_cancel, null)
            .show()
    }

    private fun openAppSettings() {
        val intent = Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            "package:$packageName".toUri(),
        )
        runCatching { startActivity(intent) }
            .onFailure {
                Toast.makeText(this, R.string.settings_unavailable, Toast.LENGTH_LONG).show()
            }
    }

    private fun openLocationSettings() {
        runCatching { startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)) }
            .onFailure {
                Toast.makeText(this, R.string.location_settings_unavailable, Toast.LENGTH_LONG).show()
            }
    }

    private fun openBatterySettings() {
        runCatching { startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
            .onFailure {
                Toast.makeText(this, R.string.battery_settings_unavailable, Toast.LENGTH_LONG).show()
            }
    }

    private fun refreshRecent() {
        val files = GpxPaths.recentFiles(this)
        llRecent.removeAllViews()
        tvRecentEmpty.visibility = if (files.isEmpty()) View.VISIBLE else View.GONE

        files.forEach { file ->
            llRecent.addView(createRecentRow(file))
        }
    }

    private fun createRecentRow(file: File): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundResource(R.drawable.bg_recent_row)
            setPadding(dp(14), dp(11), dp(8), dp(11))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply {
                bottomMargin = dp(8)
            }
        }

        val info = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f,
            )
        }

        val name = TextView(this).apply {
            text = file.name
            setTextColor(getColor(R.color.ink))
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.MIDDLE
        }
        val dateFormat = SimpleDateFormat("d MMM yyyy · HH:mm", Locale.getDefault())
        val meta = TextView(this).apply {
            text = getString(
                R.string.file_date,
                dateFormat.format(Date(file.lastModified())),
                Formatters.fileSize(file.length()),
            )
            setTextColor(getColor(R.color.ink_secondary))
            textSize = 12f
            maxLines = 1
        }

        info.addView(name)
        info.addView(meta)

        val share = Button(this).apply {
            text = getString(R.string.button_share)
            isAllCaps = false
            textSize = 13f
            setTextColor(getColor(R.color.accent))
            backgroundTintList = ColorStateList.valueOf(getColor(R.color.accent_soft))
            minWidth = 0
            minimumWidth = 0
            setPadding(dp(14), 0, dp(14), 0)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(44),
            )
            setOnClickListener { shareFile(file) }
        }

        row.addView(info)
        row.addView(share)
        return row
    }

    private fun shareFile(file: File) {
        try {
            val uri = FileProvider.getUriForFile(
                this,
                "$packageName.fileprovider",
                file,
            )
            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                type = "application/gpx+xml"
                putExtra(Intent.EXTRA_STREAM, uri)
                putExtra(Intent.EXTRA_SUBJECT, getString(R.string.share_subject, file.name))
                clipData = ClipData.newUri(contentResolver, file.name, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(shareIntent, getString(R.string.share_chooser)))
        } catch (exception: Exception) {
            Toast.makeText(this, R.string.share_error, Toast.LENGTH_LONG).show()
        }
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).toInt()
    }
}
