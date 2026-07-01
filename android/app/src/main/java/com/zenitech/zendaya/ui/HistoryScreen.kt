package com.zenitech.zendaya.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(vm: HistoryViewModel, onBack: () -> Unit) {
    val days by vm.days.collectAsStateWithLifecycle()
    val selected by vm.selected.collectAsStateWithLifecycle()
    val messages by vm.messages.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { vm.loadDays() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(selected ?: "History") },
                navigationIcon = {
                    IconButton(onClick = { if (selected != null) vm.backToDays() else onBack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (selected == null) {
                LazyColumn(Modifier.fillMaxSize()) {
                    items(days) { d ->
                        ListItem(
                            headlineContent = { Text(d.day) },
                            supportingContent = { Text("${d.count} messages") },
                            modifier = Modifier.clickable { vm.openDay(d.day) },
                        )
                        HorizontalDivider()
                    }
                }
            } else {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(messages) { m ->
                        Column {
                            Text(
                                "${m.role} · ${m.ts.substringAfter('T').take(5)} · ${m.source}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.outline,
                            )
                            Text(m.text, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
