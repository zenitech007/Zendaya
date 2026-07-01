package com.zenitech.zendaya.net

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ZendayaApi {
    @GET("api/v1/health")
    suspend fun health(): Map<String, Any>

    @POST("api/v1/chat")
    suspend fun chat(@Body req: ChatRequest): ChatResponse

    @GET("api/v1/history/days")
    suspend fun days(): DaysResponse

    @GET("api/v1/history")
    suspend fun history(@Query("day") day: String): HistoryResponse
}
