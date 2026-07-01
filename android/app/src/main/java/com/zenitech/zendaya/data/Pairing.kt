package com.zenitech.zendaya.data

import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

/** Parses the QR pairing payload {"host","port","token"} into a ServerConfig.
 *  Pure JVM (Moshi only) — no Android imports, fully unit-testable. */
object Pairing {
    @JsonClass(generateAdapter = false)
    data class QrPayload(val host: String?, val port: Int?, val token: String?)

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private val adapter = moshi.adapter(QrPayload::class.java)

    fun parse(qr: String): ServerConfig? {
        val p = try { adapter.fromJson(qr) } catch (e: Exception) { return null } ?: return null
        val host = p.host ?: return null
        val port = p.port ?: return null
        val token = p.token ?: return null
        return ServerConfig(host, port, token)
    }
}
