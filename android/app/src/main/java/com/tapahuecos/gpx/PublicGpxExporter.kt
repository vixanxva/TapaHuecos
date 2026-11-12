package com.tapahuecos.gpx

import android.Manifest
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.annotation.RequiresApi
import androidx.core.content.ContextCompat
import java.io.File
import java.io.IOException

/**
 * Copia el GPX a Documents/TapaHuecos.
 *
 * En Android 10 o superior se usa MediaStore, sin pedir permiso de
 * almacenamiento. En Android 8 y 9 se escribe directamente en la carpeta
 * pública y se necesita WRITE_EXTERNAL_STORAGE.
 */
object PublicGpxExporter {

    sealed class Result {
        data class Success(val label: String, val uri: Uri?) : Result()
        data class Failure(val message: String) : Result()
    }

    fun export(context: Context, source: File): Result {
        if (!source.isFile || source.length() == 0L) {
            return Result.Failure("El archivo GPX está vacío.")
        }

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                exportWithMediaStore(context, source)
            } else {
                exportToLegacyDocuments(context, source)
            }
        } catch (exception: Exception) {
            Result.Failure(exception.message ?: exception.javaClass.simpleName)
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun exportWithMediaStore(context: Context, source: File): Result {
        val relativePaths = listOf(
            "${Environment.DIRECTORY_DOCUMENTS}/TapaHuecos",
            "${Environment.DIRECTORY_DOWNLOADS}/TapaHuecos",
        )
        var lastFailure: Exception? = null

        for (relativePath in relativePaths) {
            try {
                val uri = copyToMediaStore(context, source, relativePath)
                return Result.Success("$relativePath/${source.name}", uri)
            } catch (exception: Exception) {
                lastFailure = exception
            }
        }

        val detail = lastFailure?.message ?: "MediaStore no aceptó el archivo."
        return Result.Failure(detail)
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun copyToMediaStore(context: Context, source: File, relativePath: String): Uri {
        val resolver = context.contentResolver
        val collection = MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, source.name)
            put(MediaStore.MediaColumns.MIME_TYPE, "application/gpx+xml")
            put(MediaStore.MediaColumns.RELATIVE_PATH, "$relativePath/")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }

        val uri = resolver.insert(collection, values)
            ?: throw IOException("No se pudo crear el documento en $relativePath.")

        try {
            val output = resolver.openOutputStream(uri, "w")
                ?: throw IOException("No se pudo abrir el documento de destino.")
            output.use { destination ->
                source.inputStream().use { input ->
                    input.copyTo(destination)
                }
            }

            val ready = ContentValues().apply {
                put(MediaStore.MediaColumns.IS_PENDING, 0)
            }
            resolver.update(uri, ready, null, null)
            return uri
        } catch (exception: Exception) {
            runCatching { resolver.delete(uri, null, null) }
            throw exception
        }
    }

    @Suppress("DEPRECATION")
    private fun exportToLegacyDocuments(context: Context, source: File): Result {
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.WRITE_EXTERNAL_STORAGE,
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return Result.Failure("Falta el permiso de almacenamiento.")
        }

        if (Environment.getExternalStorageState() != Environment.MEDIA_MOUNTED) {
            return Result.Failure("El almacenamiento externo no está disponible.")
        }

        val documents = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
        val directory = File(documents, "TapaHuecos")
        if (!directory.exists() && !directory.mkdirs()) {
            return Result.Failure("No se pudo crear Documents/TapaHuecos.")
        }

        val target = uniqueFile(directory, source.name)
        source.copyTo(target, overwrite = false)
        return Result.Success("Documents/TapaHuecos/${target.name}", uri = null)
    }

    private fun uniqueFile(directory: File, fileName: String): File {
        var candidate = File(directory, fileName)
        val baseName = fileName.substringBeforeLast('.', fileName)
        val extension = fileName.substringAfterLast('.', "")
        var suffix = 2
        while (candidate.exists()) {
            val suffixText = if (extension.isBlank()) "$baseName-$suffix" else "$baseName-$suffix.$extension"
            candidate = File(directory, suffixText)
            suffix += 1
        }
        return candidate
    }
}
