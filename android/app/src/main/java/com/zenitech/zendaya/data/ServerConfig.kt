package com.zenitech.zendaya.data

/** Pure connection config for the PC brain. No Android dependencies, so the
 *  pairing/parsing logic that produces it stays unit-testable in plain JVM. */
data class ServerConfig(val host: String, val port: Int, val token: String) {
    fun baseUrl(): String = "http://$host:$port/"
}
