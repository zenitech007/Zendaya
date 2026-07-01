package com.zenitech.zendaya

import com.zenitech.zendaya.net.*
import com.zenitech.zendaya.ui.HistoryViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class HistoryViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private val api = object : ZendayaApi {
        override suspend fun health() = mapOf<String, Any>()
        override suspend fun chat(req: ChatRequest) = ChatResponse("", "idle")
        override suspend fun days() =
            DaysResponse(listOf(DayInfo("2026-06-30", 2), DayInfo("2026-06-29", 1)))
        override suspend fun history(day: String) =
            HistoryResponse(day, listOf(
                HistoryMessage(1, day + "T08:00:00", "user", "hi", "phone")))
    }

    @Test fun loadDays_populates_days() = runTest(dispatcher) {
        val vm = HistoryViewModel(api)
        vm.loadDays()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(2, vm.days.value.size)
        assertEquals("2026-06-30", vm.days.value[0].day)
    }

    @Test fun openDay_loads_messages() = runTest(dispatcher) {
        val vm = HistoryViewModel(api)
        vm.openDay("2026-06-30")
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals("2026-06-30", vm.selected.value)
        assertEquals(1, vm.messages.value.size)
        assertEquals("hi", vm.messages.value[0].text)
    }
}
