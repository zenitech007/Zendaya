package com.zenitech.zendaya.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zenitech.zendaya.net.ChatRequest
import com.zenitech.zendaya.net.ZendayaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMsg(val role: String, val text: String)

class ChatViewModel(private val api: ZendayaApi) : ViewModel() {
    private val _messages = MutableStateFlow<List<ChatMsg>>(emptyList())
    val messages: StateFlow<List<ChatMsg>> = _messages.asStateFlow()

    private val _sending = MutableStateFlow(false)
    val sending: StateFlow<Boolean> = _sending.asStateFlow()

    fun send(text: String) {
        val msg = text.trim()
        if (msg.isEmpty() || _sending.value) return
        _messages.value = _messages.value + ChatMsg("user", msg)
        _sending.value = true
        viewModelScope.launch {
            val reply = try {
                api.chat(ChatRequest(msg)).reply
            } catch (e: Exception) {
                "[Zendaya's brain is unreachable: ${e.message}]"
            }
            _messages.value = _messages.value + ChatMsg("Zendaya", reply)
            _sending.value = false
        }
    }
}
