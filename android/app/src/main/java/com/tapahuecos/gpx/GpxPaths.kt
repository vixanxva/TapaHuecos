package com.tapahuecos.gpx

import android.content.Context
import android.os.Environment
import java.io.File
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

object GpxPaths {
    private val SESSION_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")

    /**
     * Copia de respaldo privada de la app. No requiere permisos de
     * almacenamiento y se puede compartir con FileProvider.
     */
    fun localDir(context: Context): File {
        val externalDocuments = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS)
        val directory = if (externalDocuments != null) {
            File(externalDocuments, "TapaHuecos")
        } else {
            File(context.filesDir, "gpx/TapaHuecos")
        }
        directory.mkdirs()
        return directory
    }

    fun sessionName(now: ZonedDateTime = ZonedDateTime.now()): String {
        return SESSION_FORMAT.format(now)
    }

    fun newLocalFile(context: Context): File {
        val directory = localDir(context)
        val baseName = sessionName()
        var candidate = File(directory, "$baseName.gpx")
        var suffix = 2
        while (candidate.exists()) {
            candidate = File(directory, "$baseName-$suffix.gpx")
            suffix += 1
        }
        return candidate
    }

    fun recentFiles(context: Context, limit: Int = 8): List<File> {
        return localDir(context)
            .listFiles { file -> file.isFile && file.extension.equals("gpx", ignoreCase = true) }
            ?.sortedByDescending { it.lastModified() }
            ?.take(limit)
            ?: emptyList()
    }
}
