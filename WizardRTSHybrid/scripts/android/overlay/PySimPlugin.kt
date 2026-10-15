package com.duelmasterbattle.pysim

import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.godotengine.godot.Godot
import org.godotengine.godot.plugin.GodotPlugin
import org.godotengine.godot.plugin.UsedByGodot

/**
 * Godot Android plugin "DmbPySim": runs the authoritative DuelMasterBattle world (CPython via Chaquopy) inside this app
 * so a phone can host a LAN game without a computer. GDScript reaches it with Engine.get_singleton("DmbPySim").
 *
 * The Python side is wizard_rts/net/android_entry.py: start(json) spawns the host loop in a Python thread, stop() ends
 * it, status() reports {state, port, code, secret, lan[...]} and selfTest() builds and advances a world as evidence.
 */
class PySimPlugin(godot: Godot) : GodotPlugin(godot) {
    override fun getPluginName() = "DmbPySim"

    private fun python(): Python {
        if (!Python.isStarted()) {
            val ctx = activity?.applicationContext ?: godot.getActivity()!!.applicationContext
            Python.start(AndroidPlatform(ctx))
        }
        return Python.getInstance()
    }

    private fun entry() = python().getModule("wizard_rts.net.android_entry")

    @UsedByGodot
    fun start(argsJson: String): String = try {
        entry().callAttr("start", argsJson).toString()
    } catch (e: Throwable) {
        Log.e("DmbPySim", "start failed", e)
        "{\"status\":\"rejected\",\"reason\":\"python_error\",\"detail\":\"${e.toString().replace("\"", "'")}\"}"
    }

    @UsedByGodot
    fun stop(): String = try {
        entry().callAttr("stop").toString()
    } catch (e: Throwable) {
        "{\"status\":\"rejected\",\"reason\":\"python_error\"}"
    }

    @UsedByGodot
    fun status(): String = try {
        entry().callAttr("status").toString()
    } catch (e: Throwable) {
        "{\"status\":\"rejected\",\"state\":\"failed\",\"error\":\"${e.toString().replace("\"", "'")}\"}"
    }

    @UsedByGodot
    fun logTail(lines: Int): String = try {
        entry().callAttr("log_tail", lines).toString()
    } catch (e: Throwable) {
        e.toString()
    }

    @UsedByGodot
    fun selfTest(): String = try {
        entry().callAttr("self_test").toString()
    } catch (e: Throwable) {
        Log.e("DmbPySim", "self test failed", e)
        "{\"status\":\"rejected\",\"reason\":\"python_error\",\"detail\":\"${e.toString().replace("\"", "'")}\"}"
    }

    @UsedByGodot
    fun pythonVersion(): String = try {
        python().getModule("sys").get("version").toString()
    } catch (e: Throwable) {
        e.toString()
    }
}
