package com.zenitech.zendaya

import com.zenitech.zendaya.data.Pairing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingTest {
    @Test fun parses_valid_qr_json() {
        val cfg = Pairing.parse("""{"host":"100.1.2.3","port":7475,"token":"abc"}""")
        assertEquals("100.1.2.3", cfg!!.host)
        assertEquals(7475, cfg.port)
        assertEquals("abc", cfg.token)
        assertEquals("http://100.1.2.3:7475/", cfg.baseUrl())
    }

    @Test fun returns_null_on_garbage() {
        assertNull(Pairing.parse("not json"))
    }

    @Test fun returns_null_when_field_missing() {
        assertNull(Pairing.parse("""{"host":"100.1.2.3","port":7475}"""))
    }
}
