package com.zenitech.zendaya.ui

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import com.zenitech.zendaya.data.ConfigStore
import com.zenitech.zendaya.net.ApiClient

private sealed interface Screen {
    data object Chat : Screen
    data object History : Screen
}

@Composable
fun ZendayaApp() {
    val ctx = LocalContext.current
    var config by remember { mutableStateOf(ConfigStore.load(ctx)) }
    var screen by remember { mutableStateOf<Screen>(Screen.Chat) }

    val cfg = config
    if (cfg == null) {
        PairingScreen(onPaired = {
            ConfigStore.save(ctx, it)
            config = it
        })
        return
    }

    val api = remember(cfg) { ApiClient.create(cfg) }
    val chatVm = remember(api) { ChatViewModel(api) }
    val historyVm = remember(api) { HistoryViewModel(api) }

    when (screen) {
        Screen.Chat -> ChatScreen(chatVm, onOpenHistory = { screen = Screen.History })
        Screen.History -> HistoryScreen(historyVm, onBack = { screen = Screen.Chat })
    }
}
