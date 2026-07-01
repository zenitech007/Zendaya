package com.zenitech.zendaya.net

data class ChatRequest(val message: String)
data class ChatResponse(val reply: String, val state: String?)

data class DayInfo(val day: String, val count: Int)
data class DaysResponse(val days: List<DayInfo>)

data class HistoryMessage(
    val id: Long,
    val ts: String,
    val role: String,
    val text: String,
    val source: String,
)
data class HistoryResponse(val day: String, val messages: List<HistoryMessage>)
