package com.example.minicpm_v_demo.harness

import android.content.Context
import com.example.minicpm_v_demo.LlamaEngine
import com.example.minicpm_v_demo.ModelDownloadService

class LlamaDownloadManager(private val context: Context) {

    suspend fun downloadSelectedModel(onProgress: (String) -> Unit) {
        LlamaEngine.downloadModels(context, onProgress)
    }

    fun startForegroundDownload() {
        ModelDownloadService.start(context)
    }

    fun cancelForegroundDownload() {
        ModelDownloadService.cancel(context)
    }
}
