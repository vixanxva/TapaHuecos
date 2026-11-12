package com.tapahuecos.gpx

import java.util.Locale
import java.util.concurrent.TimeUnit

object Formatters {

    fun duration(elapsedMillis: Long): String {
        val safeMillis = elapsedMillis.coerceAtLeast(0L)
        val totalSeconds = TimeUnit.MILLISECONDS.toSeconds(safeMillis)
        val hours = totalSeconds / 3600
        val minutes = (totalSeconds % 3600) / 60
        val seconds = totalSeconds % 60
        return String.format(Locale.US, "%02d:%02d:%02d", hours, minutes, seconds)
    }

    fun distance(meters: Double): String {
        val safeMeters = meters.coerceAtLeast(0.0)
        return if (safeMeters < 1_000.0) {
            String.format(Locale.getDefault(), "%.0f m", safeMeters)
        } else {
            String.format(Locale.getDefault(), "%.2f km", safeMeters / 1_000.0)
        }
    }

    fun accuracy(meters: Float?): String? {
        if (meters == null || !meters.isFinite() || meters < 0f) return null
        return String.format(Locale.getDefault(), "%.0f m", meters)
    }

    fun fileSize(bytes: Long): String {
        val safeBytes = bytes.coerceAtLeast(0L)
        return when {
            safeBytes < 1_024L -> "$safeBytes B"
            safeBytes < 1_048_576L -> String.format(Locale.getDefault(), "%.0f KB", safeBytes / 1_024.0)
            else -> String.format(Locale.getDefault(), "%.1f MB", safeBytes / 1_048_576.0)
        }
    }
}
