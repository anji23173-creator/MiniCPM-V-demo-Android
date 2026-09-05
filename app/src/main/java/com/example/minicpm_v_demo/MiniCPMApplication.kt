package com.example.minicpm_v_demo

import android.app.Application
import android.util.Log
import com.example.minicpm_v_demo.harness.data.AssetBootstrapper

class MiniCPMApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        LocaleManager.applyOnAppStart(this)
        try {
            AssetBootstrapper.bootstrap(this)
        } catch (error: Exception) {
            Log.e("MiniCPMApplication", "Failed to bootstrap harness assets", error)
        }
    }
}
