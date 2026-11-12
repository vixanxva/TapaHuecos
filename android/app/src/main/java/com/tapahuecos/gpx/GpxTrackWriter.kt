package com.tapahuecos.gpx

import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile
import java.nio.charset.StandardCharsets
import java.time.Instant
import java.util.Locale

/**
 * Escritor GPX 1.1 incremental.
 *
 * Después de abrir el archivo y después de cada punto, el documento contiene
 * sus etiquetas de cierre. Así, si Android mata el proceso o se agota la
 * batería, el GPX sigue siendo un XML válido y conserva los puntos ya escritos.
 */
class GpxTrackWriter private constructor(
    val file: File,
    private val randomAccessFile: RandomAccessFile,
    private var tailOffset: Long,
) : Closeable {

    var pointCount: Int = 0
        private set

    private var closed = false

    @Synchronized
    fun addPoint(point: GpxPoint): Boolean {
        if (closed || !isValid(point)) return false

        val pointBytes = pointToXml(point).toByteArray(StandardCharsets.UTF_8)
        // Punto y cierre en una sola escritura: con dos, si Android mataba el proceso
        // entre ambas, el archivo quedaba sin </gpx> y no se podía leer ningún punto.
        randomAccessFile.seek(tailOffset)
        randomAccessFile.write(pointBytes + FOOTER_BYTES)
        tailOffset += pointBytes.size
        randomAccessFile.setLength(tailOffset + FOOTER_BYTES.size)
        randomAccessFile.fd.sync()
        pointCount += 1
        return true
    }

    @Synchronized
    override fun close() {
        if (closed) return
        closed = true
        randomAccessFile.close()
    }

    companion object {
        private const val CREATOR = "TapaHuecos GPX Android 1.0"

        private const val FOOTER = """</trkseg>
</trk>
</gpx>
"""
        private val FOOTER_BYTES = FOOTER.toByteArray(StandardCharsets.UTF_8)

        fun create(file: File, sessionName: String, startedAtMillis: Long): GpxTrackWriter {
            file.parentFile?.mkdirs()
            val randomAccessFile = RandomAccessFile(file, "rw")
            randomAccessFile.setLength(0)

            val header = buildHeader(sessionName, startedAtMillis)
            val headerBytes = header.toByteArray(StandardCharsets.UTF_8)
            randomAccessFile.write(headerBytes)
            randomAccessFile.write(FOOTER_BYTES)
            randomAccessFile.fd.sync()

            return GpxTrackWriter(
                file = file,
                randomAccessFile = randomAccessFile,
                tailOffset = headerBytes.size.toLong(),
            )
        }

        private fun buildHeader(sessionName: String, startedAtMillis: Long): String {
            val safeName = escapeXml(sessionName)
            val startTime = Instant.ofEpochMilli(startedAtMillis).toString()
            return """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1"
     creator="$CREATOR"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xmlns:th="https://tapahuecos.local/gpx/1"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>$safeName</name>
    <desc>Recorrido vial grabado con TapaHuecos GPX</desc>
    <time>$startTime</time>
  </metadata>
  <trk>
    <name>$safeName</name>
    <trkseg>
"""
        }

        private fun isValid(point: GpxPoint): Boolean {
            return point.latitude.isFinite() &&
                point.longitude.isFinite() &&
                point.latitude in -90.0..90.0 &&
                point.longitude in -180.0..180.0 &&
                point.timeMillis > 0
        }

        private fun pointToXml(point: GpxPoint): String {
            val xml = StringBuilder(256)
            xml.append("    <trkpt lat=\"")
                .append(String.format(Locale.US, "%.7f", point.latitude))
                .append("\" lon=\"")
                .append(String.format(Locale.US, "%.7f", point.longitude))
                .append("\">\n")

            point.elevationMeters
                ?.takeIf { it.isFinite() }
                ?.let { xml.append("      <ele>").append(String.format(Locale.US, "%.1f", it)).append("</ele>\n") }

            xml.append("      <time>")
                .append(Instant.ofEpochMilli(point.timeMillis).toString())
                .append("</time>\n")

            val accuracy = point.accuracyMeters?.takeIf { it.isFinite() && it >= 0f }
            val speed = point.speedMetersPerSecond?.takeIf { it.isFinite() && it >= 0f }
            val provider = point.provider?.takeIf { it.isNotBlank() }

            if (accuracy != null || speed != null || provider != null) {
                xml.append("      <extensions>\n")
                accuracy?.let {
                    xml.append("        <th:accuracy>")
                        .append(String.format(Locale.US, "%.1f", it))
                        .append("</th:accuracy>\n")
                }
                speed?.let {
                    xml.append("        <th:speed>")
                        .append(String.format(Locale.US, "%.2f", it))
                        .append("</th:speed>\n")
                }
                provider?.let {
                    xml.append("        <th:provider>")
                        .append(escapeXml(it))
                        .append("</th:provider>\n")
                }
                xml.append("      </extensions>\n")
            }

            xml.append("    </trkpt>\n")
            return xml.toString()
        }

        private fun escapeXml(value: String): String {
            return buildString(value.length) {
                value.forEach { character ->
                    when (character) {
                        '&' -> append("&amp;")
                        '<' -> append("&lt;")
                        '>' -> append("&gt;")
                        '"' -> append("&quot;")
                        '\'' -> append("&apos;")
                        else -> append(character)
                    }
                }
            }
        }
    }
}
