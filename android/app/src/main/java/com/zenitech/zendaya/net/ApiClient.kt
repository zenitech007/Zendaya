package com.zenitech.zendaya.net

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.zenitech.zendaya.data.ServerConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    fun create(cfg: ServerConfig): ZendayaApi {
        val auth = Interceptor { chain ->
            val req = chain.request().newBuilder()
                .addHeader("Authorization", "Bearer ${cfg.token}")
                .build()
            chain.proceed(req)
        }
        val ok = OkHttpClient.Builder()
            .addInterceptor(auth)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)  // chat turns can be slow
            .build()
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        return Retrofit.Builder()
            .baseUrl(cfg.baseUrl())
            .client(ok)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(ZendayaApi::class.java)
    }
}
