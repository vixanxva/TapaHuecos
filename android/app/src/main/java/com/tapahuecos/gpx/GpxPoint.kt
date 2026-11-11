package com.tapahuecos.gpx

/**
 * Un punto de un recorrido. No depende de las clases de Android para que el
 * escritor GPX se pueda probar en la JVM.
 */
data class GpxPoint(
    val latitude: Double,
    val longitude: Double,
    val timeMillis: Long,
    val elevationMeters: Double? = null,
    val accuracyMeters: Float? = null,
    val speedMetersPerSecond: Float? = null,
    val provider: String? = null,
)
