package com.zenitech.zendaya.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Persists the paired ServerConfig in EncryptedSharedPreferences. Android-only
 *  (needs a Context + Keystore), so it is exercised by the on-device test, not
 *  the JVM unit suite. */
object ConfigStore {
    private const val FILE = "zendaya_secure_prefs"
    private const val K_HOST = "host"
    private const val K_PORT = "port"
    private const val K_TOKEN = "token"

    private fun prefs(ctx: Context) =
        EncryptedSharedPreferences.create(
            ctx,
            FILE,
            MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )

    fun save(ctx: Context, cfg: ServerConfig) {
        prefs(ctx).edit()
            .putString(K_HOST, cfg.host)
            .putInt(K_PORT, cfg.port)
            .putString(K_TOKEN, cfg.token)
            .apply()
    }

    fun load(ctx: Context): ServerConfig? {
        val p = prefs(ctx)
        val host = p.getString(K_HOST, null) ?: return null
        val token = p.getString(K_TOKEN, null) ?: return null
        val port = p.getInt(K_PORT, 0)
        if (port == 0) return null
        return ServerConfig(host, port, token)
    }
}
