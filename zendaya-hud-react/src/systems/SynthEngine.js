/**
 * SynthEngine.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Procedural synth — generates ALL Zendaya SFX via Web Audio API.
 * No audio files required. Every sound is spec-accurate.
 *
 * Covers: Interaction Layer (§5), Transition Layer (§6),
 *         Intelligence Layer (§7), Alert System (§10),
 *         Orb state transitions (§4), Success Resolution (§7).
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { AudioManager } from "./AudioManager";
class SynthEngineSingleton {
    get ctx() { return AudioManager.ctx; }
    // ── Connect a chain of nodes → layer gain ────────────────────────────────
    connect(node, layer) {
        const layerGain = AudioManager.getLayerGain(layer);
        if (layerGain)
            node.connect(layerGain);
    }
    // ── Utility: create a master gain for a synth voice ──────────────────────
    makeVoiceGain(layer, initial = 0) {
        if (!this.ctx)
            return null;
        const g = this.ctx.createGain();
        g.gain.value = initial;
        this.connect(g, layer);
        return g;
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §5  INTERACTION SOUNDS
    // ────────────────────────────────────────────────────────────────────────────
    playInteraction(type) {
        switch (type) {
            case "hover":
                this._hover();
                break;
            case "click":
                this._click();
                break;
            case "confirm":
                this._confirm();
                break;
            case "open":
                this._open();
                break;
            case "close":
                this._close();
                break;
            case "dock":
                this._dock();
                break;
            case "error":
                this._uiError();
                break;
        }
    }
    /** Soft holographic tick — hover */
    _hover() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = 880;
        osc.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.06, t + 0.008);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.07);
        osc.start(t);
        osc.stop(t + 0.08);
    }
    /** Futuristic tap — click */
    _click() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(620, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(280, ctx.currentTime + 0.06);
        osc.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.18, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
        osc.start(t);
        osc.stop(t + 0.1);
    }
    /** Bright harmonic pulse — confirm */
    _confirm() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const freqs = [523, 659, 784]; // C5 E5 G5 — bright major chord
        const t = ctx.currentTime;
        freqs.forEach((f, i) => {
            const g = this.makeVoiceGain("interaction");
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.value = f;
            osc.connect(g);
            const start = t + i * 0.04;
            g.gain.setValueAtTime(0, start);
            g.gain.linearRampToValueAtTime(0.14, start + 0.02);
            g.gain.exponentialRampToValueAtTime(0.0001, start + 0.28);
            osc.start(start);
            osc.stop(start + 0.3);
        });
    }
    /** Expanding energy sweep — open panel */
    _open() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "sawtooth";
        const filter = ctx.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(400, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(3200, ctx.currentTime + 0.22);
        filter.Q.value = 2;
        osc.frequency.setValueAtTime(160, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(480, ctx.currentTime + 0.22);
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.18, t + 0.04);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
        osc.start(t);
        osc.stop(t + 0.3);
    }
    /** Descending filtered fade — close panel */
    _close() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "sawtooth";
        const filter = ctx.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(2800, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.2);
        filter.Q.value = 1.5;
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(140, ctx.currentTime + 0.2);
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.16, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
        osc.start(t);
        osc.stop(t + 0.26);
    }
    /** Mechanical magnetic lock — dock */
    _dock() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Two-layered: low thud + high click
        [{ f: 90, type: "sine", dur: 0.12, amp: 0.28 },
            { f: 1200, type: "square", dur: 0.05, amp: 0.10 }]
            .forEach(({ f, type, dur, amp }) => {
            const g = this.makeVoiceGain("interaction");
            const osc = ctx.createOscillator();
            osc.type = type;
            osc.frequency.value = f;
            osc.connect(g);
            const t = ctx.currentTime;
            g.gain.setValueAtTime(amp, t);
            g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
            osc.start(t);
            osc.stop(t + dur + 0.01);
        });
    }
    /** Distorted UI error */
    _uiError() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "square";
        const dist = ctx.createWaveShaper();
        dist.curve = this._makeDistCurve(60);
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.setValueAtTime(180, ctx.currentTime + 0.08);
        osc.connect(dist);
        dist.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.12, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
        osc.start(t);
        osc.stop(t + 0.23);
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §6  TRANSITION SOUNDS
    // ────────────────────────────────────────────────────────────────────────────
    playTransitionSweep(type) {
        switch (type) {
            case "expand":
                this._expandSweep();
                break;
            case "contract":
                this._contractSweep();
                break;
            case "minimize":
                this._minimizeSweep();
                break;
            case "restore":
                this._restoreSweep();
                break;
            case "scene":
                this._sceneSweep();
                break;
        }
    }
    _expandSweep() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("transition");
        const osc = ctx.createOscillator();
        const filter = ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.Q.value = 3;
        filter.frequency.setValueAtTime(200, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(4000, ctx.currentTime + 0.6);
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(80, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(640, ctx.currentTime + 0.6);
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.22, t + 0.1);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.7);
        osc.start(t);
        osc.stop(t + 0.75);
    }
    _contractSweep() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("transition");
        const osc = ctx.createOscillator();
        osc.type = "sawtooth";
        const filter = ctx.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(3000, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.45);
        osc.frequency.setValueAtTime(560, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(70, ctx.currentTime + 0.45);
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.20, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
        osc.start(t);
        osc.stop(t + 0.52);
    }
    _minimizeSweep() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("transition");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(110, ctx.currentTime + 0.35);
        osc.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.15, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.38);
        osc.start(t);
        osc.stop(t + 0.4);
    }
    _restoreSweep() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        const g = this.makeVoiceGain("transition");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.35);
        osc.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.15, t + 0.05);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
        osc.start(t);
        osc.stop(t + 0.42);
    }
    _sceneSweep() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Wide stereo sweep — panned L then R
        [-0.5, 0.5].forEach((pan, i) => {
            const g = this.makeVoiceGain("transition");
            const panner = ctx.createStereoPanner();
            panner.pan.value = pan;
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.setValueAtTime(440 + i * 80, ctx.currentTime);
            osc.connect(panner);
            panner.connect(g);
            const t = ctx.currentTime + i * 0.04;
            g.gain.setValueAtTime(0, t);
            g.gain.linearRampToValueAtTime(0.12, t + 0.06);
            g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
            osc.start(t);
            osc.stop(t + 0.42);
        });
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §4  ORB STATE SOUNDS
    // ────────────────────────────────────────────────────────────────────────────
    playOrbState(state) {
        switch (state) {
            case "idle":
                this._orbIdle();
                break;
            case "listening":
                this._orbListening();
                break;
            case "thinking":
                this._orbThinking();
                break;
            case "speaking":
                this._orbSpeaking();
                break;
        }
    }
    _orbIdle() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Soft breathing pulse + faint harmonic
        const g = this.makeVoiceGain("orb");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = 55; // 55 Hz — sub-bass foundation
        const osc2 = ctx.createOscillator();
        osc2.type = "sine";
        osc2.frequency.value = 110;
        const g2 = ctx.createGain();
        g2.gain.value = 0.4;
        osc.connect(g);
        osc2.connect(g2);
        g2.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.08, t + 0.4);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 1.8);
        osc.start(t);
        osc.stop(t + 1.9);
        osc2.start(t);
        osc2.stop(t + 1.9);
    }
    _orbListening() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Pitch rises, sonar-like ping
        const g = this.makeVoiceGain("orb");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.3);
        const filter = ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.Q.value = 8;
        filter.frequency.value = 660;
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.22, t + 0.05);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.7);
        osc.start(t);
        osc.stop(t + 0.75);
    }
    _orbThinking() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Dense modulated texture — rapid data-scan feel
        const t = ctx.currentTime;
        const modFreqs = [180, 240, 320, 420];
        modFreqs.forEach((f, i) => {
            const g = this.makeVoiceGain("orb");
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.value = f;
            const lfo = ctx.createOscillator();
            lfo.type = "sine";
            lfo.frequency.value = 4 + i * 1.5;
            const lfoGain = ctx.createGain();
            lfoGain.gain.value = f * 0.08;
            lfo.connect(lfoGain);
            lfoGain.connect(osc.frequency);
            osc.connect(g);
            const start = t + i * 0.06;
            g.gain.setValueAtTime(0, start);
            g.gain.linearRampToValueAtTime(0.06, start + 0.08);
            g.gain.exponentialRampToValueAtTime(0.0001, start + 0.5);
            osc.start(start);
            lfo.start(start);
            osc.stop(start + 0.55);
            lfo.stop(start + 0.55);
        });
    }
    _orbSpeaking() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Warm resonance bloom — merges orb with voice intent
        const g = this.makeVoiceGain("orb");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = 330;
        const filter = ctx.createBiquadFilter();
        filter.type = "peaking";
        filter.frequency.value = 1200;
        filter.gain.value = 6;
        filter.Q.value = 1.5;
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.18, t + 0.15);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.9);
        osc.start(t);
        osc.stop(t + 0.95);
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §7  SUCCESS RESOLUTION
    // ────────────────────────────────────────────────────────────────────────────
    playSuccessResolution() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Upward harmonic resolution — subconscious satisfaction (spec §7)
        const t = ctx.currentTime;
        const notes = [
            { f: 392, start: 0, dur: 0.5 }, // G4
            { f: 494, start: 0.1, dur: 0.45 }, // B4
            { f: 587, start: 0.2, dur: 0.4 }, // D5
            { f: 784, start: 0.3, dur: 0.6 }, // G5 — resolution
        ];
        notes.forEach(({ f, start, dur }) => {
            const g = this.makeVoiceGain("orb");
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.value = f;
            osc.connect(g);
            const s = t + start;
            g.gain.setValueAtTime(0, s);
            g.gain.linearRampToValueAtTime(0.11, s + 0.04);
            g.gain.exponentialRampToValueAtTime(0.0001, s + dur);
            osc.start(s);
            osc.stop(s + dur + 0.01);
        });
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §5  DOCK / UNDOCK SPECIAL SOUNDS
    // ────────────────────────────────────────────────────────────────────────────
    playDockSound() {
        this.playInteraction("dock");
    }
    playUndockSound() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Reverse of dock — magnetic release
        const g = this.makeVoiceGain("interaction");
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.setValueAtTime(90, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(560, ctx.currentTime + 0.15);
        osc.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.18, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
        osc.start(t);
        osc.stop(t + 0.22);
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §5  NOTIFICATION PING
    // ────────────────────────────────────────────────────────────────────────────
    playNotificationPing() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // "Intelligent pulse" — two-tone gentle ping
        const t = ctx.currentTime;
        [{ f: 1047, start: 0 }, { f: 1319, start: 0.08 }].forEach(({ f, start }) => {
            const g = this.makeVoiceGain("alert");
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.value = f;
            osc.connect(g);
            const s = t + start;
            g.gain.setValueAtTime(0, s);
            g.gain.linearRampToValueAtTime(0.18, s + 0.015);
            g.gain.exponentialRampToValueAtTime(0.0001, s + 0.35);
            osc.start(s);
            osc.stop(s + 0.37);
        });
    }
    // ────────────────────────────────────────────────────────────────────────────
    // §10  ALERT SYSTEM
    // ────────────────────────────────────────────────────────────────────────────
    playAlert(type) {
        switch (type) {
            case "info":
                this._alertInfo();
                break;
            case "warning":
                this._alertWarning();
                break;
            case "critical":
                this._alertCritical();
                break;
            case "error":
                this._alertError();
                break;
        }
    }
    _alertInfo() {
        // Soft pulse — barely audible
        this.playNotificationPing();
    }
    _alertWarning() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Low-frequency alert — present but not alarming (spec §10)
        const g = this.makeVoiceGain("alert");
        const osc = ctx.createOscillator();
        osc.type = "triangle";
        osc.frequency.value = 180;
        const filter = ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.frequency.value = 400;
        filter.Q.value = 2;
        osc.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.25, t + 0.06);
        g.gain.setValueAtTime(0.25, t + 0.18);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
        osc.start(t);
        osc.stop(t + 0.6);
    }
    _alertCritical() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Distorted resonant tone — spec §10
        const g = this.makeVoiceGain("alert");
        const osc = ctx.createOscillator();
        osc.type = "sawtooth";
        osc.frequency.value = 150;
        const dist = ctx.createWaveShaper();
        dist.curve = this._makeDistCurve(80);
        const filter = ctx.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.value = 800;
        filter.Q.value = 5;
        osc.connect(dist);
        dist.connect(filter);
        filter.connect(g);
        const t = ctx.currentTime;
        // Two pulses — communicates urgency without repetitive alarm
        [0, 0.3].forEach((offset) => {
            g.gain.setValueAtTime(0, t + offset);
            g.gain.linearRampToValueAtTime(0.28, t + offset + 0.04);
            g.gain.exponentialRampToValueAtTime(0.0001, t + offset + 0.22);
        });
        osc.start(t);
        osc.stop(t + 0.6);
    }
    _alertError() {
        const ctx = this.ctx;
        if (!ctx)
            return;
        // Glitch modulation — spec §10 "System failure: glitch modulation"
        const g = this.makeVoiceGain("alert");
        const osc = ctx.createOscillator();
        osc.type = "square";
        const dist = ctx.createWaveShaper();
        dist.curve = this._makeDistCurve(100);
        osc.connect(dist);
        dist.connect(g);
        const t = ctx.currentTime;
        // Rapid frequency glitch
        [200, 140, 220, 100, 240].forEach((f, i) => {
            osc.frequency.setValueAtTime(f, t + i * 0.04);
        });
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.20, t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
        osc.start(t);
        osc.stop(t + 0.35);
    }
    // ── Distortion curve helper ───────────────────────────────────────────────
    _makeDistCurve(amount) {
        const n = 256;
        const curve = new Float32Array(n);
        const k = amount;
        for (let i = 0; i < n; i++) {
            const x = (i * 2) / n - 1;
            curve[i] = ((Math.PI + k) * x) / (Math.PI + k * Math.abs(x));
        }
        return curve;
    }
}
export const SynthEngine = new SynthEngineSingleton();
