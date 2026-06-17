/**
 * MIXI-CUT Web Demo — Pure JavaScript Decoder
 *
 * Decodes MIXI-CUT timecode WAV files in the browser using Web Audio API.
 * Includes a complete JS port of the Bandpass→PLL→MassSpring pipeline.
 */

'use strict';

// ── Protocol Constants ──────────────────────────────────────

const CARRIER = 3000;
const SR = 44100;
const BLOCK = 128;
const TAU = 2 * Math.PI;

// ── Bandpass Filter ─────────────────────────────────────────

class Bandpass {
    constructor(freq = CARRIER, sr = SR, q = 2.5) {
        const w0 = TAU * Math.min(freq, sr * 0.45) / sr;
        const alpha = Math.sin(w0) / (2 * Math.max(q, 0.1));
        const a0 = 1 + alpha;
        this.b0 = alpha / a0;
        this.b2 = -alpha / a0;
        this.a1 = -2 * Math.cos(w0) / a0;
        this.a2 = (1 - alpha) / a0;
        this.z1 = 0;
        this.z2 = 0;
    }

    tick(x) {
        const y = this.b0 * x + this.z1;
        this.z1 = -this.a1 * y + this.z2;
        this.z2 = this.b2 * x - this.a2 * y;
        return y;
    }

    reset() { this.z1 = 0; this.z2 = 0; }
}

// ── PLL ─────────────────────────────────────────────────────

class PLL {
    constructor(freq = CARRIER, sr = SR, bwPct = 0.08) {
        this.center = freq;
        this.sr = sr;
        this.phase = 0;
        this.freq = freq;
        this.integral = 0;
        this.lock = 0;
        const bw = freq * bwPct;
        const omega = TAU * bw / sr;
        this.kp = 2 * omega;
        this.ki = omega * omega;
    }

    tick(l, r) {
        const amp = Math.sqrt(l * l + r * r);
        if (amp < 0.005) {
            const a = 1 / (this.sr * 0.05);
            this.lock *= (1 - a);
            this.phase += TAU * this.freq / this.sr;
            if (this.phase >= TAU) this.phase -= TAU;
            return [this.freq / this.center, this.lock];
        }

        let err = Math.atan2(l, r) - this.phase;
        if (err > Math.PI) err -= TAU;
        else if (err < -Math.PI) err += TAU;

        const drain = this.lock < 0.3 ? 0.98 : 1.0;
        this.integral = Math.max(-this.center * 0.5,
            Math.min(this.center * 0.5, this.integral * drain + err * this.ki));
        this.freq = Math.max(-this.center * 2,
            Math.min(this.center * 3, this.center + err * this.kp * this.sr + this.integral));

        this.phase += TAU * this.freq / this.sr;
        if (this.phase >= TAU) this.phase -= TAU;
        else if (this.phase < 0) this.phase += TAU;

        const a = 1 / (this.sr * 0.05);
        this.lock = this.lock * (1 - a) + Math.cos(err) * a;
        return [this.freq / this.center, Math.max(0, Math.min(1, this.lock))];
    }

    reset() { this.phase = 0; this.freq = this.center; this.integral = 0; this.lock = 0; }
}

// ── Mass-Spring ─────────────────────────────────────────────

class MassSpring {
    constructor(inertia = 0.95) {
        this.speed = 0; this.prev = 0;
        this.traction = 1 - inertia;
        this.scratching = false; this.release = 0;
        this.decelCount = 0; this.prevInput = 0;
    }

    tick(v) {
        this.prev = this.speed;
        const d = Math.abs(v - this.speed);

        if (d > 0.3) {
            this.speed = v; this.scratching = true; this.release = 0;
        } else if (this.scratching) {
            this.speed = this.speed * 0.3 + v * 0.7;
            if (d < 0.05) { this.release++; if (this.release > 20) this.scratching = false; }
            else this.release = 0;
        } else {
            if (v < this.prevInput - 0.001 && this.speed > 0.05) this.decelCount++;
            else this.decelCount = Math.max(0, this.decelCount - 2);

            let t;
            if (this.decelCount > 3) {
                const bf = Math.min((this.decelCount - 3) / 5, 1);
                t = 0.5 + bf * 0.4;
            } else if (Math.abs(v) < 0.1 && d > 0.05) {
                t = Math.min(this.traction * 10, 0.5);
            } else {
                t = this.traction;
            }
            this.speed = this.speed * (1 - t) + v * t;
        }
        this.prevInput = v;
        if (Math.abs(this.speed) < 0.02 && Math.abs(v) < 0.02) this.speed = 0;
        return this.speed;
    }

    reset() { this.speed = 0; this.prev = 0; this.scratching = false;
              this.release = 0; this.decelCount = 0; this.prevInput = 0; }
}

// ── Decoder ─────────────────────────────────────────────────

class Decoder {
    constructor(freq = CARRIER, sr = SR) {
        this.freq = freq; this.sr = sr;
        this.bpL = new Bandpass(freq, sr); this.bpR = new Bandpass(freq, sr);
        this.pll = new PLL(freq, sr); this.ms = new MassSpring();
        this.pos = 0;
    }

    process(left, right) {
        const n = left.length;
        let ss = 0, sl = 0, se = 0;
        for (let i = 0; i < n; i++) {
            const fl = this.bpL.tick(left[i]);
            const fr = this.bpR.tick(right[i]);
            const [spd, lk] = this.pll.tick(fl, fr);
            this.pos += this.pll.freq / this.sr;
            ss += spd; sl += lk; se += fl * fl + fr * fr;
        }
        const avgS = ss / n, avgL = sl / n, rms = Math.sqrt(se / n);
        const speedIn = rms > 0.01 ? avgS : 0;
        return { speed: this.ms.tick(speedIn), lock: avgL, position: this.pos / this.freq };
    }

    reset() { this.bpL.reset(); this.bpR.reset(); this.pll.reset(); this.ms.reset(); this.pos = 0; }
}

// ── App ─────────────────────────────────────────────────────

const app = {
    decoder: null,
    audioCtx: null,
    audioBuffer: null,
    source: null,
    isPlaying: false,
    startTime: 0,
    speedHistory: [],
    lockHistory: [],
    activeTab: 'speed',
    leftChannel: null,
    rightChannel: null,
    results: [],

    init() {
        this.setupDropZone();
        this.setupControls();
        this.setupTabs();
        live.init();
        document.getElementById('btn-live').addEventListener('click', () => live.enter());
    },

    setMode(mode) {
        // mode: 'file' | 'live'
        document.getElementById('file-controls').classList.toggle('hidden', mode !== 'file');
        document.getElementById('live-controls').classList.toggle('hidden', mode !== 'live');
        document.getElementById('deck').classList.toggle('hidden', mode !== 'live');
        document.getElementById('info-mode').textContent =
            mode === 'live' ? 'LIVE / DVS rel.' : '24-bit + RS(4)';
    },

    setupDropZone() {
        const dz = document.getElementById('drop-zone');
        const fi = document.getElementById('file-input');

        dz.addEventListener('click', () => fi.click());
        dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
        dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
        dz.addEventListener('drop', e => {
            e.preventDefault();
            dz.classList.remove('dragover');
            if (e.dataTransfer.files.length) this.loadFile(e.dataTransfer.files[0]);
        });
        fi.addEventListener('change', e => { if (e.target.files.length) this.loadFile(e.target.files[0]); });
    },

    setupControls() {
        document.getElementById('btn-play').addEventListener('click', () => this.play());
        document.getElementById('btn-stop').addEventListener('click', () => this.stop());
        document.getElementById('btn-reset').addEventListener('click', () => this.reset());
    },

    setupTabs() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.activeTab = tab.dataset.tab;
                this.drawGraph();
            });
        });
    },

    async loadFile(file) {
        // Timecode must be lossless: MP3/AAC/OGG joint-stereo perceptual coding
        // wrecks the L=sin / R=cos quadrature the decoder locks onto.
        if (!/\.(wav|flac|aif|aiff)$/i.test(file.name)) {
            alert('Use a lossless file (WAV / FLAC / AIFF).\n\n' +
                  'Lossy formats (MP3, AAC, OGG…) destroy the L/R quadrature ' +
                  'phase of the 3 kHz timecode — the decoder will not lock.');
            return;
        }

        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SR });
        const arrayBuffer = await file.arrayBuffer();
        this.audioBuffer = await this.audioCtx.decodeAudioData(arrayBuffer);

        this.leftChannel = this.audioBuffer.getChannelData(0);
        this.rightChannel = this.audioBuffer.numberOfChannels > 1
            ? this.audioBuffer.getChannelData(1)
            : this.audioBuffer.getChannelData(0);

        const dur = this.audioBuffer.duration;
        document.getElementById('file-info').textContent =
            `${file.name} — ${this.audioBuffer.sampleRate} Hz, ${this.audioBuffer.numberOfChannels} ch, ${dur.toFixed(1)}s`;

        // Decode entire file
        this.decodeFile();

        // Show dashboard (file mode)
        this.setMode('file');
        document.getElementById('drop-zone').classList.add('hidden');
        document.getElementById('dashboard').classList.remove('hidden');
        document.getElementById('btn-play').disabled = false;
        document.getElementById('playback-time').textContent =
            `0:00 / ${Math.floor(dur / 60)}:${String(Math.floor(dur % 60)).padStart(2, '0')}`;
    },

    decodeFile() {
        this.decoder = new Decoder(CARRIER, this.audioBuffer.sampleRate);
        this.results = [];
        this.speedHistory = [];
        this.lockHistory = [];

        const left = this.leftChannel;
        const right = this.rightChannel;
        const n = left.length;

        for (let i = 0; i < n; i += BLOCK) {
            const end = Math.min(i + BLOCK, n);
            const lBlock = left.subarray(i, end);
            const rBlock = right.subarray(i, end);
            const r = this.decoder.process(lBlock, rBlock);
            this.results.push(r);
            this.speedHistory.push(r.speed);
            this.lockHistory.push(r.lock);
        }

        // Update final gauges
        const last = this.results[this.results.length - 1];
        if (last) this.updateGauges(last);
        this.drawGraph();
    },

    updateGauges(r) {
        document.getElementById('gauge-speed').innerHTML =
            `${r.speed.toFixed(3)}<span class="gauge-unit">x</span>`;
        document.getElementById('gauge-lock').textContent = r.lock.toFixed(3);
        document.getElementById('gauge-position').innerHTML =
            `${r.position.toFixed(2)}<span class="gauge-unit">s</span>`;

        const speedPct = Math.min(Math.abs(r.speed) / 2 * 100, 100);
        const lockPct = Math.max(0, Math.min(r.lock * 100, 100));
        const posPct = this.audioBuffer
            ? Math.min(r.position / this.audioBuffer.duration * 100, 100) : 0;

        document.getElementById('speed-bar').style.width = speedPct + '%';
        document.getElementById('lock-bar').style.width = lockPct + '%';
        document.getElementById('pos-bar').style.width = posPct + '%';

        // Color coding for lock
        const lockEl = document.getElementById('gauge-lock');
        if (r.lock > 0.8) lockEl.style.color = '#10b981';
        else if (r.lock > 0.5) lockEl.style.color = '#f59e0b';
        else lockEl.style.color = '#ef4444';
    },

    drawGraph() {
        const canvas = document.getElementById('graph-canvas');
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        canvas.width = canvas.clientWidth * dpr;
        canvas.height = canvas.clientHeight * dpr;
        ctx.scale(dpr, dpr);

        const w = canvas.clientWidth;
        const h = canvas.clientHeight;

        // Background
        ctx.fillStyle = '#0a0a0f';
        ctx.fillRect(0, 0, w, h);

        // Grid
        ctx.strokeStyle = '#1a1a25';
        ctx.lineWidth = 1;
        for (let y = 0; y < h; y += h / 5) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }

        let data, color, label, range;
        if (this.activeTab === 'speed') {
            data = this.speedHistory;
            color = '#00d4ff';
            label = 'Speed';
            range = [-0.5, 2.0];
        } else if (this.activeTab === 'lock') {
            data = this.lockHistory;
            color = '#10b981';
            label = 'Lock';
            range = [0, 1.1];
        } else {
            // Waveform: downsample left channel
            const left = this.leftChannel;
            if (!left) return;
            const ds = Math.max(1, Math.floor(left.length / w));
            data = [];
            for (let i = 0; i < left.length; i += ds) data.push(left[i]);
            color = '#8b5cf6';
            label = 'Waveform';
            range = [-1, 1];
        }

        if (!data || data.length < 2) return;

        // Draw curve
        const gradient = ctx.createLinearGradient(0, 0, w, 0);
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, color + '80');

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;

        for (let i = 0; i < data.length; i++) {
            const x = (i / data.length) * w;
            const y = h - ((data[i] - range[0]) / (range[1] - range[0])) * h;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Fill under curve
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        const fillGrad = ctx.createLinearGradient(0, 0, 0, h);
        fillGrad.addColorStop(0, color + '20');
        fillGrad.addColorStop(1, color + '02');
        ctx.fillStyle = fillGrad;
        ctx.fill();

        // Playhead during playback
        if (this.isPlaying && this.audioCtx) {
            const elapsed = this.audioCtx.currentTime - this.startTime;
            const progress = elapsed / this.audioBuffer.duration;
            const px = progress * w;
            ctx.strokeStyle = '#ffffff80';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(px, 0);
            ctx.lineTo(px, h);
            ctx.stroke();
        }

        // Label
        ctx.fillStyle = '#555568';
        ctx.font = '11px JetBrains Mono';
        ctx.fillText(label, 8, 16);
    },

    play() {
        if (this.isPlaying) return;
        if (!this.audioCtx || !this.audioBuffer) return;

        if (this.audioCtx.state === 'suspended') this.audioCtx.resume();

        this.source = this.audioCtx.createBufferSource();
        this.source.buffer = this.audioBuffer;
        this.source.connect(this.audioCtx.destination);
        this.startTime = this.audioCtx.currentTime;
        this.source.start();
        this.isPlaying = true;

        document.getElementById('btn-play').disabled = true;
        document.getElementById('btn-stop').disabled = false;

        // Update gauges in real-time during playback
        this._animFrame = null;
        const animate = () => {
            if (!this.isPlaying) return;
            const elapsed = this.audioCtx.currentTime - this.startTime;
            const blockIdx = Math.floor(elapsed * this.audioBuffer.sampleRate / BLOCK);

            if (blockIdx >= 0 && blockIdx < this.results.length) {
                this.updateGauges(this.results[blockIdx]);
            }

            const dur = this.audioBuffer.duration;
            const min = Math.floor(elapsed / 60);
            const sec = Math.floor(elapsed % 60);
            const tMin = Math.floor(dur / 60);
            const tSec = Math.floor(dur % 60);
            document.getElementById('playback-time').textContent =
                `${min}:${String(sec).padStart(2, '0')} / ${tMin}:${String(tSec).padStart(2, '0')}`;

            this.drawGraph();

            if (elapsed < dur) {
                this._animFrame = requestAnimationFrame(animate);
            } else {
                this.stop();
            }
        };
        this._animFrame = requestAnimationFrame(animate);

        this.source.onended = () => this.stop();
    },

    stop() {
        if (this.source) {
            try { this.source.stop(); } catch (_) {}
            this.source = null;
        }
        this.isPlaying = false;
        if (this._animFrame) cancelAnimationFrame(this._animFrame);

        document.getElementById('btn-play').disabled = false;
        document.getElementById('btn-stop').disabled = true;
        this.drawGraph();
    },

    reset() {
        this.stop();
        if (this.audioCtx) { this.audioCtx.close(); this.audioCtx = null; }
        this.audioBuffer = null;
        this.results = [];
        this.speedHistory = [];
        this.lockHistory = [];
        this.leftChannel = null;
        this.rightChannel = null;

        document.getElementById('drop-zone').classList.remove('hidden');
        document.getElementById('dashboard').classList.add('hidden');
    }
};

// ── Live input + DVS deck ───────────────────────────────────
//
// Real-time decode of a turntable feed: stereo line-in → ScriptProcessor
// runs the same Bandpass→PLL→MassSpring pipeline block by block. The decoded
// signed speed drives a fractional read-pointer into an uploaded track buffer
// (relative DVS), so moving/scratching the vinyl moves the track — including
// reverse and pitch. Browser DSP (AGC/echo/noise) MUST be off or the timecode
// is destroyed.

const LIVE_LOCK_GATE = 0.12;   // below this lock, freeze the deck (needle lifted / noise)
const LIVE_BLOCK = 64;         // decode granularity within each audio callback (~1.5 ms)

const live = {
    ctx: null,
    stream: null,
    micNode: null,
    proc: null,
    monitorGain: null,
    decoder: null,
    running: false,

    // deck (track driven by the vinyl)
    deckL: null,
    deckR: null,
    deckLen: 0,
    deckPos: 0,
    motor: true,

    // shared state written on the audio thread, read by the UI loop
    latest: { speed: 0, lock: 0 },
    inLevel: 0,
    stereoWarned: false,
    raf: null,

    init() {
        document.getElementById('btn-mic').addEventListener('click', () => this.startInput());
        document.getElementById('btn-mic-stop').addEventListener('click', () => this.stopInput());
        document.getElementById('btn-live-back').addEventListener('click', () => this.leave());
        document.getElementById('btn-deck-load').addEventListener('click', () =>
            document.getElementById('deck-input').click());
        document.getElementById('deck-input').addEventListener('change', e => {
            if (e.target.files.length) this.loadDeck(e.target.files[0]);
        });
        document.getElementById('btn-deck-cue').addEventListener('click', () => { this.deckPos = 0; });
        document.getElementById('deck-motor').addEventListener('change', e => {
            this.motor = e.target.checked;
        });
        document.getElementById('deck-vol').addEventListener('input', e => {
            if (this.monitorGain) this.monitorGain.gain.value = e.target.value / 100;
        });
    },

    enter() {
        app.setMode('live');
        document.getElementById('drop-zone').classList.add('hidden');
        document.getElementById('dashboard').classList.remove('hidden');
        document.getElementById('file-info').innerHTML =
            '🎚 <b>Live mode</b> — press <b>Start input</b> and grant mic/line-in access, ' +
            'then load a track. Use a <b>stereo</b> line-in with a phono pre (or cut the ' +
            '<code>phono</code> preset and go direct).';
    },

    leave() {
        this.stopInput();
        document.getElementById('dashboard').classList.add('hidden');
        document.getElementById('drop-zone').classList.remove('hidden');
    },

    async startInput() {
        if (this.running) return;
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                    channelCount: 2,
                    sampleRate: SR,
                },
                video: false,
            });
        } catch (err) {
            alert('Could not open audio input: ' + err.message +
                  '\n\nNeeds HTTPS (or localhost) and a granted line-in.');
            return;
        }

        this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SR });
        if (this.ctx.state === 'suspended') await this.ctx.resume();

        this.decoder = new Decoder(CARRIER, this.ctx.sampleRate);
        this.micNode = this.ctx.createMediaStreamSource(this.stream);
        this.proc = this.ctx.createScriptProcessor(2048, 2, 2);
        this.monitorGain = this.ctx.createGain();
        this.monitorGain.gain.value = document.getElementById('deck-vol').value / 100;

        this.proc.onaudioprocess = e => this.process(e);

        this.micNode.connect(this.proc);
        this.proc.connect(this.monitorGain);
        this.monitorGain.connect(this.ctx.destination);

        // reset histories so the graph starts clean
        app.speedHistory = [];
        app.lockHistory = [];
        app.results = [];

        this.running = true;
        this.stereoWarned = false;
        document.getElementById('btn-mic').disabled = true;
        document.getElementById('btn-mic-stop').disabled = false;
        document.getElementById('file-info').innerHTML =
            `🟢 <b>Listening</b> — ${this.ctx.sampleRate} Hz. Drop the needle on the timecode.`;

        this.loopUI();
    },

    stopInput() {
        this.running = false;
        if (this.raf) cancelAnimationFrame(this.raf);
        if (this.proc) { try { this.proc.disconnect(); } catch (_) {} this.proc.onaudioprocess = null; this.proc = null; }
        if (this.micNode) { try { this.micNode.disconnect(); } catch (_) {} this.micNode = null; }
        if (this.monitorGain) { try { this.monitorGain.disconnect(); } catch (_) {} this.monitorGain = null; }
        if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
        if (this.ctx) { this.ctx.close(); this.ctx = null; }
        document.getElementById('btn-mic').disabled = false;
        document.getElementById('btn-mic-stop').disabled = true;
    },

    async loadDeck(file) {
        const tmpCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SR });
        const buf = await tmpCtx.decodeAudioData(await file.arrayBuffer());
        this.deckL = buf.getChannelData(0);
        this.deckR = buf.numberOfChannels > 1 ? buf.getChannelData(1) : this.deckL;
        this.deckLen = buf.length;
        this.deckPos = 0;
        tmpCtx.close();
        const dur = buf.duration;
        document.getElementById('deck-status').textContent =
            `${file.name} — ${Math.floor(dur / 60)}:${String(Math.floor(dur % 60)).padStart(2, '0')}`;
        document.getElementById('btn-deck-cue').disabled = false;
    },

    // sampleRate of deck == ctx SR, so speed 1.0 advances exactly 1 sample/sample
    sampleDeck(ch, pos) {
        const i = Math.floor(pos);
        if (i < 0 || i + 1 >= this.deckLen) return 0;
        const f = pos - i;
        return ch[i] * (1 - f) + ch[i + 1] * f;
    },

    process(e) {
        const inL = e.inputBuffer.getChannelData(0);
        const inR = e.inputBuffer.numberOfChannels > 1
            ? e.inputBuffer.getChannelData(1) : inL;
        const outL = e.outputBuffer.getChannelData(0);
        const outR = e.outputBuffer.getChannelData(1);
        const n = inL.length;

        let level = 0, diff = 0;
        let o = 0;
        const haveDeck = this.deckL && this.deckLen > 0;

        for (let i = 0; i < n; i += LIVE_BLOCK) {
            const end = Math.min(i + LIVE_BLOCK, n);
            const r = this.decoder.process(inL.subarray(i, end), inR.subarray(i, end));
            this.latest = r;

            const gated = r.lock > LIVE_LOCK_GATE ? r.speed : 0;
            const step = this.motor ? gated : 1; // motor off = straight 1x playback

            for (let j = i; j < end; j++) {
                const a = Math.abs(inL[j]);
                if (a > level) level = a;
                const d = inL[j] - inR[j];
                diff += d < 0 ? -d : d;

                let sl = 0, sr = 0;
                if (haveDeck && (step !== 0)) {
                    this.deckPos += step;
                    if (this.deckPos < 0) this.deckPos = 0;
                    else if (this.deckPos >= this.deckLen - 1) this.deckPos = this.deckLen - 1;
                    sl = this.sampleDeck(this.deckL, this.deckPos);
                    sr = this.sampleDeck(this.deckR, this.deckPos);
                }
                outL[o] = sl; outR[o] = sr; o++;
            }
        }
        this.inLevel = level;
        // crude mono detection: L and R essentially identical → not real stereo
        if (!this.stereoWarned && level > 0.02 && diff / n < 1e-4) {
            this.stereoWarned = true;
            document.getElementById('file-info').innerHTML =
                '⚠️ <b>Input looks MONO</b> — the timecode is L=sin / R=cos quadrature and ' +
                'needs a true stereo line-in. Decode will not lock.';
        }
    },

    loopUI() {
        if (!this.running) return;
        const r = this.latest;
        app.updateGauges({ speed: r.speed, lock: r.lock, position: this.deckPos / SR });
        app.speedHistory.push(r.speed);
        app.lockHistory.push(r.lock);
        if (app.speedHistory.length > 1200) { app.speedHistory.shift(); app.lockHistory.shift(); }
        app.results.push({ speed: r.speed, lock: r.lock, position: this.deckPos / SR });
        if (app.results.length > 1200) app.results.shift();

        document.getElementById('input-meter-fill').style.width =
            Math.min(this.inLevel * 140, 100) + '%';
        if (this.deckLen > 0) {
            document.getElementById('deck-progress-fill').style.width =
                (this.deckPos / this.deckLen * 100) + '%';
        }
        app.drawGraph();
        this.raf = requestAnimationFrame(() => this.loopUI());
    },
};

// Boot
document.addEventListener('DOMContentLoaded', () => app.init());
