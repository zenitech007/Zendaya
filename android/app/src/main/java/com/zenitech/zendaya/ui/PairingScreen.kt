package com.zenitech.zendaya.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.zenitech.zendaya.data.Pairing
import com.zenitech.zendaya.data.ServerConfig

@Composable
fun PairingScreen(onPaired: (ServerConfig) -> Unit) {
    var error by remember { mutableStateOf<String?>(null) }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val contents = result.contents
        if (contents == null) { error = "Scan cancelled"; return@rememberLauncherForActivityResult }
        val cfg = Pairing.parse(contents)
        if (cfg == null) error = "That QR code isn't a valid Zendaya pairing code."
        else onPaired(cfg)
    }

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Pair with Zendaya", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text(
            "On your PC, run the pairing QR helper and scan it here.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))
        Button(onClick = {
            scanner.launch(ScanOptions().setOrientationLocked(false)
                .setPrompt("Scan the Zendaya pairing QR"))
        }) { Text("Scan QR code") }
        error?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
    }
}
