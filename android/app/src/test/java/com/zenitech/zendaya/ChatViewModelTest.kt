package com.zenitech.zendaya

import com.zenitech.zendaya.net.*
import com.zenitech.zendaya.ui.ChatViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun fakeApi(reply: String) = object : ZendayaApi {
        override suspend fun health() = mapOf<String, Any>("ok" to true)
        override suspend fun chat(req: ChatRequest) = ChatResponse(reply, "idle")
        override suspend fun days() = DaysResponse(emptyList())
        override suspend fun history(day: String) = HistoryResponse(day, emptyList())
    }

    @Test fun send_appends_user_then_reply() = runTest(dispatcher) {
        val vm = ChatViewModel(fakeApi("pong"))
        vm.send("ping")
        dispatcher.scheduler.advanceUntilIdle()
        val msgs = vm.messages.value
        assertEquals(2, msgs.size)
        assertEquals("user", msgs[0].role)
        assertEquals("ping", msgs[0].text)
        assertEquals("Zendaya", msgs[1].role)
        assertEquals("pong", msgs[1].text)
    }
}
