package com.tapahuecos.gpx

import java.io.File
import java.time.Instant
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.w3c.dom.Document

class GpxTrackWriterTest {

    @get:Rule
    val temporaryFolder = TemporaryFolder()

    private val startedAt = Instant.parse("2026-11-11T17:00:00Z").toEpochMilli()

    @Test
    fun `el archivo es valido antes y despues de cada punto`() {
        val file = temporaryFolder.newFile("20261111-120000.gpx")
        val writer = GpxTrackWriter.create(file, "20261111-120000", startedAt)

        assertValidGpx(file, expectedPoints = 0)

        val first = GpxPoint(
            latitude = 8.748,
            longitude = -75.881,
            timeMillis = Instant.parse("2026-11-11T17:00:01Z").toEpochMilli(),
            elevationMeters = 12.4,
            accuracyMeters = 4.5f,
            speedMetersPerSecond = 8.25f,
            provider = "gps",
        )
        assertTrue(writer.addPoint(first))
        assertValidGpx(file, expectedPoints = 1)

        val second = first.copy(
            latitude = 8.7481,
            timeMillis = Instant.parse("2026-11-11T17:00:02Z").toEpochMilli(),
        )
        assertTrue(writer.addPoint(second))
        assertValidGpx(file, expectedPoints = 2)
        assertEquals(2, writer.pointCount)

        writer.close()

        val document = parse(file)
        assertEquals("gpx", document.documentElement.tagName)
        val point = document.getElementsByTagName("trkpt").item(0)
        val element = point as org.w3c.dom.Element
        assertEquals("8.7480000", element.getAttribute("lat"))
        assertEquals("-75.8810000", element.getAttribute("lon"))

        val accuracy = document
            .getElementsByTagNameNS("https://tapahuecos.local/gpx/1", "accuracy")
            .item(0)
            .textContent
        assertEquals("4.5", accuracy)
    }

    @Test
    fun `rechaza coordenadas invalidas sin romper el documento`() {
        val file = temporaryFolder.newFile("invalido.gpx")
        val writer = GpxTrackWriter.create(file, "invalido", startedAt)

        assertFalse(
            writer.addPoint(
                GpxPoint(
                    latitude = 120.0,
                    longitude = -75.0,
                    timeMillis = startedAt,
                ),
            ),
        )
        assertFalse(
            writer.addPoint(
                GpxPoint(
                    latitude = 8.0,
                    longitude = Double.NaN,
                    timeMillis = startedAt,
                ),
            ),
        )
        assertValidGpx(file, expectedPoints = 0)
        writer.close()
    }

    @Test
    fun `escapa el nombre de la sesion`() {
        val file = temporaryFolder.newFile("escape.gpx")
        val writer = GpxTrackWriter.create(file, "ruta & <prueba>", startedAt)
        writer.close()

        val document = parse(file)
        val metadataName = document.getElementsByTagName("metadata").item(0)
            .childNodes
        val names = (0 until metadataName.length)
            .map { metadataName.item(it) }
            .filter { it.nodeName == "name" }
        assertEquals(1, names.size)
        assertEquals("ruta & <prueba>", names.first().textContent)
    }

    private fun assertValidGpx(file: File, expectedPoints: Int) {
        val document = parse(file)
        assertEquals(expectedPoints, document.getElementsByTagName("trkpt").length)
        assertEquals(1, document.getElementsByTagName("trkseg").length)
    }

    private fun parse(file: File): Document {
        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
        }
        return factory.newDocumentBuilder().parse(file)
    }
}
