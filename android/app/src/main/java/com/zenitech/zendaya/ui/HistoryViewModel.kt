package com.zenitech.zendaya.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zenitech.zendaya.net.DayInfo
import com.zenitech.zendaya.net.HistoryMessage
import com.zenitech.zendaya.net.ZendayaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class HistoryViewModel(private val api: ZendayaApi) : ViewModel() {
    private val _days = MutableStateFlow<List<DayInfo>>(emptyList())
    val days: StateFlow<List<DayInfo>> = _days.asStateFlow()

    private val _selected = MutableStateFlow<String?>(null)
    val selected: StateFlow<String?> = _selected.asStateFlow()

    private val _messages = MutableStateFlow<List<HistoryMessage>>(emptyList())
    val messages: StateFlow<List<HistoryMessage>> = _messages.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    fun loadDays() {
        _loading.value = true
        viewModelScope.launch {
            _days.value = try { api.days().days } catch (e: Exception) { emptyList() }
            _loading.value = false
        }
    }

    fun openDay(day: String) {
        _selected.value = day
        _loading.value = true
        viewModelScope.launch {
            _messages.value = try { api.history(day).messages } catch (e: Exception) { emptyList() }
            _loading.value = false
        }
    }

    fun backToDays() { _selected.value = null }
}
