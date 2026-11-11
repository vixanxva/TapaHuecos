package com.tapahuecos.gpx

enum class RecordingPhase {
    IDLE,
    RECORDING,
    SAVING,
    ERROR,
}

data class RecordingSnapshot(
    val phase: RecordingPhase = RecordingPhase.IDLE,
    val startedAtMillis: Long = 0L,
    val elapsedMillis: Long = 0L,
    val pointCount: Int = 0,
    val distanceMeters: Double = 0.0,
    val accuracyMeters: Float? = null,
    val fileName: String? = null,
    val exportLabel: String? = null,
    val exportError: String? = null,
    val lastError: String? = null,
) {
    companion object {
        fun idle(): RecordingSnapshot = RecordingSnapshot()
    }
}
