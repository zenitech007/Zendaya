package com.zenitech.zendaya

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.zenitech.zendaya.net.ChatResponse
import com.zenitech.zendaya.net.HistoryResponse
import org.junit.Assert.assertEquals
import org.junit.Test

class ApiModelsTest {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test fun parses_chat_response() {
        val a = moshi.adapter(ChatResponse::class.java)
        val r = a.fromJson("""{"reply":"hi there","state":"idle"}""")!!
        assertEquals("hi there", r.reply)
        assertEquals("idle", r.state)
    }

    @Test fun parses_history_response() {
        val a = moshi.adapter(HistoryResponse::class.java)
        val json = """{"day":"2026-06-30","messages":[
            {"id":1,"ts":"2026-06-30T08:00:00","role":"user","text":"hello","source":"phone"}]}"""
        val r = a.fromJson(json)!!
        assertEquals("2026-06-30", r.day)
        assertEquals(1, r.messages.size)
        assertEquals("hello", r.messages[0].text)
        assertEquals("phone", r.messages[0].source)
    }
}
