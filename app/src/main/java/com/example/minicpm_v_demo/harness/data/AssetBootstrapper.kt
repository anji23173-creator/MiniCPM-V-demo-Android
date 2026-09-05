package com.example.minicpm_v_demo.harness.data

import android.content.Context
import java.io.File

object AssetBootstrapper {
    private const val ASSET_ROOT = "harness"

    fun bootstrap(context: Context): HarnessDataPaths {
        val paths = HarnessDataPaths.from(context.applicationContext)
        paths.ensureRuntimeDirs()
        copyAssetDirectory(context, ASSET_ROOT, paths.rootDir)
        return paths
    }

    fun bootstrapFromDirectory(sourceRoot: File, paths: HarnessDataPaths) {
        require(sourceRoot.isDirectory) { "Harness asset directory does not exist: ${sourceRoot.absolutePath}" }
        paths.ensureRuntimeDirs()
        sourceRoot.walkTopDown().forEach { source ->
            val relative = source.relativeTo(sourceRoot).path
            if (relative.isEmpty()) return@forEach
            val target = File(paths.rootDir, relative)
            if (source.isDirectory) {
                check(target.isDirectory || target.mkdirs()) { "Failed to create ${target.absolutePath}" }
            } else {
                target.parentFile?.mkdirs()
                source.copyTo(target, overwrite = true)
            }
        }
    }

    private fun copyAssetDirectory(context: Context, assetPath: String, targetDir: File) {
        val children = context.assets.list(assetPath).orEmpty()
        check(targetDir.isDirectory || targetDir.mkdirs()) { "Failed to create ${targetDir.absolutePath}" }
        for (name in children) {
            val childAssetPath = "$assetPath/$name"
            val childNames = context.assets.list(childAssetPath).orEmpty()
            if (childNames.isNotEmpty()) {
                copyAssetDirectory(context, childAssetPath, File(targetDir, name))
            } else {
                val target = File(targetDir, name)
                target.parentFile?.mkdirs()
                context.assets.open(childAssetPath).use { input ->
                    target.outputStream().use { output -> input.copyTo(output) }
                }
            }
        }
    }
}
