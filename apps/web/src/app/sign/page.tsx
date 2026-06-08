"use client";

/**
 * Digital Human — Multi-modal Sign / gesture studio with continuous, voice-enabled chat.
 *
 * ONE camera + ONE pretrained model (Google MediaPipe Gesture Recognizer, tasks-vision) powers
 * THREE input modes the user picks between:
 *   1) Gestures   — 7 pretrained gestures → MOEI phrases (zero training, instant).
 *   2) Fingerspell — hand landmarks → finger pattern → letter (A–Z / Arabic), builds words.
 *   3) Type        — keyboard fallback, always works (no camera needed).
 *
 * The recognizer returns BOTH `gestures` and `landmarks`, so modes 1 & 2 share the same model.
 * All three feed ONE continuous, context-aware conversation with voice output. EN + AR toggle.
 * Fully client-side; video never leaves the device.
 *   Model: ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer
 */

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Send, Trash2, Volume2, Camera as CamIcon, RotateCcw, MessageCircle, Hand, Keyboard,
  Sparkles, SpellCheck,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// ── Mode 1: pretrained-gesture → MOEI phrase dictionary (bilingual + emoji) ──
type Gesture = { key: string; emoji: string; en: string; ar: string };
const GESTURES: Gesture[] = [
  { key: "Open_Palm",   emoji: "🖐️", en: "Hello",              ar: "مرحبا" },
  { key: "Thumb_Up",    emoji: "👍", en: "Yes",                ar: "نعم" },
  { key: "Thumb_Down",  emoji: "👎", en: "No",                 ar: "لا" },
  { key: "Pointing_Up", emoji: "☝️", en: "I need help",        ar: "أحتاج مساعدة" },
  { key: "Victory",     emoji: "✌️", en: "Check my status",    ar: "حالة طلبي" },
  { key: "Closed_Fist", emoji: "✊", en: "I have a complaint", ar: "لدي شكوى" },
  { key: "ILoveYou",    emoji: "🤟", en: "Thank you",          ar: "شكرا" },
];
const GESTURE_BY_KEY = Object.fromEntries(GESTURES.map((g) => [g.key, g]));

// ── Mode 2: finger-pattern → letter. Deterministic & self-documenting (chart shown). ──
// pattern = [thumb,index,middle,ring,pinky] up/down. "00000" (fist) = space/commit word.
const EN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const AR_LETTERS = "ا ب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه و ي".split(" ");
const ALPHABET: { pattern: string; en: string; ar: string }[] = AR_LETTERS.map((ar, i) => ({
  pattern: (i + 1).toString(2).padStart(5, "0"), // 1.."11100" — 00000 reserved for space
  en: EN_LETTERS[i] || "",
  ar,
}));
const LETTER_BY_PATTERN = Object.fromEntries(ALPHABET.map((a) => [a.pattern, a]));

const HOLD_GESTURE = 10;   // frames to commit a gesture (~0.5s)
const HOLD_LETTER = 8;     // frames to commit a letter
const SPACE_FRAMES = 6;    // fist frames to commit a word
const AUTOSEND_MS = 2500;  // pause auto-sends (gesture mode)
const MIN_SCORE = 0.5;

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const ESM = "https://esm.sh/@mediapipe/tasks-vision@0.10.18";

type Mode = "gesture" | "spell" | "type";
type ChatMsg = { role: "user" | "assistant"; text: string; time: string };

export default function SignPage() {
  return (
    <LoginGate
      title="Sign-Language Assistant"
      subtitle="Gestures, fingerspelling, or text — one screen, continuous voice chat. Sign in with UAE PASS."
    >
      {(session) => <SignExperience session={session} />}
    </LoginGate>
  );
}

function SignExperience({ session }: { session: UaePassSession }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [mode, setMode] = useState<Mode>("gesture");
  const [status, setStatus] = useState("Loading gesture model…");
  const [live, setLive] = useState<{ label: string; sub: string; score: number } | null>(null);
  const [hold, setHold] = useState(0);
  const [tokens, setTokens] = useState<string[]>([]);   // committed words/phrases (display text)
  const [letters, setLetters] = useState<string[]>([]); // current word being spelled
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState("");
  const [sessionId] = useState(() => "sign-" + (session.emirates_id || "anon") + "-" + Date.now());

  // refs for the rAF loop / async send
  const tokensRef = useRef<string[]>([]);
  const lettersRef = useRef<string[]>([]);
  const lastAtRef = useRef(Date.now());
  const busyRef = useRef(false);
  const langRef = useRef(language);
  const modeRef = useRef(mode);
  useEffect(() => { tokensRef.current = tokens; }, [tokens]);
  useEffect(() => { lettersRef.current = letters; }, [letters]);
  useEffect(() => { busyRef.current = busy; }, [busy]);
  useEffect(() => { langRef.current = language; }, [language]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Silence MediaPipe's benign WASM INFO logs so Next's dev overlay doesn't flag them as errors.
  useEffect(() => {
    const orig = console.error;
    console.error = (...args: any[]) => {
      const s = String(args[0] ?? "");
      if (s.includes("XNNPACK") || s.startsWith("INFO:") || s.includes("TensorFlow Lite") || s.includes("GL version") || s.includes("Created TensorFlow")) return;
      orig(...args);
    };
    return () => { console.error = orig; };
  }, []);

  // ── send text to the assistant (continuous session) ──
  const send = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || busyRef.current) return;
    const lang = langRef.current;
    setBusy(true);
    setTokens([]); setLetters([]);
    lastAtRef.current = Date.now();
    setMessages((m) => [...m, { role: "user", text: t, time: new Date().toLocaleTimeString() }]);
    try {
      const r = await fetch(`${API_URL}/chat/web`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: session.emirates_id || "anonymous",
          channel: "web", session_id: sessionId, language: lang, text: t,
        }),
      });
      const d = await r.json();
      const reply = d.text || "…";
      setMessages((m) => [...m, { role: "assistant", text: reply, time: new Date().toLocaleTimeString() }]);
      speak(reply, lang);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Connection error. Please try again.", time: new Date().toLocaleTimeString() }]);
    } finally {
      setBusy(false);
    }
  }, [session.emirates_id, sessionId]);

  // Build the outgoing text from committed tokens + any half-spelled word.
  const sendCurrent = useCallback(() => {
    const tail = lettersRef.current.join("");
    const all = [...tokensRef.current, ...(tail ? [tail] : [])];
    send(all.join(" "));
  }, [send]);

  function speak(text: string, lang: "en" | "ar") {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang === "ar" || /[؀-ۿ]/.test(text) ? "ar-AE" : "en-US";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }
  }

  // ── pause → auto-send (gesture mode only; spell uses the Send button) ──
  useEffect(() => {
    const id = setInterval(() => {
      if (modeRef.current === "gesture" && tokensRef.current.length > 0 && !busyRef.current && Date.now() - lastAtRef.current > AUTOSEND_MS) {
        sendCurrent();
      }
    }, 400);
    return () => clearInterval(id);
  }, [sendCurrent]);

  // ── MediaPipe pretrained recognizer loop (gestures + landmarks) ──
  useEffect(() => {
    let recognizer: any, stream: MediaStream | null = null, raf = 0, cancelled = false;
    let lastVideoTime = -1;
    // gesture commit state
    let gKey = "", gHold = 0, gCommitted = false;
    // letter commit state
    let lPat = "", lHold = 0, lCommitted = false, fistFrames = 0;

    function fingersUp(lm: any[]): string {
      const up = (tip: number, pip: number) => (lm[tip].y < lm[pip].y ? "1" : "0");
      const thumb = Math.abs(lm[4].x - lm[5].x) > 0.08 && lm[4].y < lm[6].y ? "1" : "0";
      return thumb + up(8, 6) + up(12, 10) + up(16, 14) + up(20, 18);
    }

    async function init() {
      try {
        const vision: any = await (Function("u", "return import(u)")(ESM));
        const { GestureRecognizer, FilesetResolver } = vision;
        const fileset = await FilesetResolver.forVisionTasks(WASM);
        recognizer = await GestureRecognizer.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL, delegate: "GPU" },
          runningMode: "VIDEO",
          numHands: 1,
        });
        if (cancelled) return;
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 540, height: 405 }, audio: false });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        const video = videoRef.current!;
        video.srcObject = stream;
        await video.play();
        setReady(true);
        setStatus("Ready");
        loop();
      } catch {
        setError("Could not load the model or camera. Allow camera access and use Chrome/Edge — or use Type mode below.");
        setStatus("Camera unavailable — use Type mode");
      }
    }

    function loop() {
      if (cancelled) return;
      const video = videoRef.current, cv = canvasRef.current;
      if (video && cv && video.readyState >= 2) {
        const ctx = cv.getContext("2d");
        if (ctx) {
          ctx.clearRect(0, 0, cv.width, cv.height);
          ctx.drawImage(video, 0, 0, cv.width, cv.height);
          if (video.currentTime !== lastVideoTime) {
            lastVideoTime = video.currentTime;
            let res: any;
            try { res = recognizer.recognizeForVideo(video, performance.now()); } catch {}

            const lms = res?.landmarks?.[0];
            if (lms) {
              ctx.fillStyle = "#9c8853";
              for (const p of lms) { ctx.beginPath(); ctx.arc(p.x * cv.width, p.y * cv.height, 3, 0, 6.28); ctx.fill(); }
            }

            const m = modeRef.current;
            if (m === "gesture") {
              const g = res?.gestures?.[0]?.[0];
              const key = g?.categoryName, score = g?.score ?? 0;
              if (key && key !== "None" && key !== "Unknown" && GESTURE_BY_KEY[key] && score >= MIN_SCORE) {
                const gi = GESTURE_BY_KEY[key];
                setLive({ label: `${gi.emoji} ${gi[langRef.current]}`, sub: `${Math.round(score * 100)}%`, score });
                if (key === gKey) {
                  gHold++; setHold(gHold);
                  if (gHold >= HOLD_GESTURE && !gCommitted) {
                    gCommitted = true;
                    setTokens((t) => [...t, gi[langRef.current]]);
                    lastAtRef.current = Date.now();
                    setStatus(`Added: ${gi.en}`);
                  }
                } else { gKey = key; gHold = 0; gCommitted = false; setHold(0); }
              } else { setLive(null); gKey = ""; gHold = 0; gCommitted = false; setHold(0); }
            } else if (m === "spell") {
              if (lms) {
                const pat = fingersUp(lms);
                if (pat === "00000") { // fist = space / commit current word
                  fistFrames++;
                  setLive({ label: "✊ space", sub: "commit word", score: 1 });
                  if (fistFrames >= SPACE_FRAMES) {
                    if (lettersRef.current.length) {
                      const w = lettersRef.current.join("");
                      setTokens((t) => [...t, w]); setLetters([]);
                      lastAtRef.current = Date.now(); setStatus(`Word: ${w}`);
                    }
                    fistFrames = -999; // require release before next space
                  }
                  lPat = ""; lHold = 0; lCommitted = false; setHold(0);
                } else {
                  fistFrames = 0;
                  const entry = LETTER_BY_PATTERN[pat];
                  const ch = entry ? entry[langRef.current] : "";
                  if (ch) {
                    setLive({ label: ch, sub: pat, score: 1 });
                    if (pat === lPat) {
                      lHold++; setHold(lHold);
                      if (lHold >= HOLD_LETTER && !lCommitted) {
                        lCommitted = true;
                        setLetters((l) => [...l, ch]);
                        setStatus(`Letter: ${ch}`);
                      }
                    } else { lPat = pat; lHold = 0; lCommitted = false; setHold(0); }
                  } else { setLive(null); lPat = ""; lHold = 0; lCommitted = false; setHold(0); }
                }
              } else { setLive(null); lPat = ""; lHold = 0; lCommitted = false; fistFrames = 0; setHold(0); }
            }
          }
        }
      }
      raf = requestAnimationFrame(loop);
    }

    init();
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      try { stream?.getTracks().forEach((t) => t.stop()); } catch {}
      try { recognizer?.close(); } catch {}
    };
  }, []);

  const draftText = [...tokens, ...(letters.length ? [letters.join("")] : [])];

  return (
    <div className="bg-moei-cream/30 min-h-screen flex flex-col">
      {/* header */}
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="moei-kicker">Accessibility · Digital Human</span>
              <h1 className="mt-1 moei-h-section">Multi-modal Sign Studio</h1>
              <p className="mt-1 max-w-2xl text-sm text-moei-body">
                Choose how to communicate — pretrained gestures, fingerspelling, or text — all in one
                continuous, voice-enabled conversation. English (ASL) + Arabic (ArSL).
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setLanguage(language === "en" ? "ar" : "en")} className="moei-btn-secondary">
                {language === "en" ? "العربية" : "English"}
              </button>
              <button onClick={() => { setMessages([]); setTokens([]); setLetters([]); }} className="moei-btn-secondary">
                <RotateCcw size={14} /> Clear chat
              </button>
            </div>
          </div>

          {/* mode selector */}
          <div className="mt-4 inline-flex flex-wrap rounded-xl border border-moei-line bg-moei-cream/40 p-1">
            {([
              { k: "gesture", icon: Sparkles, label: "Gestures", hint: "pretrained" },
              { k: "spell", icon: SpellCheck, label: "Fingerspell", hint: "A–Z / أ–ي" },
              { k: "type", icon: Keyboard, label: "Type", hint: "always works" },
            ] as const).map(({ k, icon: Icon, label, hint }) => (
              <button
                key={k}
                onClick={() => { setMode(k); setLive(null); setHold(0); }}
                className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                  mode === k ? "bg-moei-bronze text-white" : "text-moei-body hover:text-moei-bronze"
                }`}
              >
                <Icon size={15} /> {label}
                <span className={`ml-1 text-[10px] font-normal ${mode === k ? "text-white/80" : "text-moei-muted"}`}>· {hint}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="flex-1 mx-auto max-w-7xl px-6 py-6 w-full">
        <div className="grid gap-6 lg:grid-cols-3">
          {/* left: camera (gesture/spell) or big text box (type) + draft */}
          <div className="lg:col-span-2 space-y-4">
            {mode !== "type" ? (
              <div className="rounded-2xl border border-moei-line bg-white p-4">
                <div className="relative overflow-hidden rounded-xl bg-slate-900" style={{ aspectRatio: "4/3" }}>
                  <video ref={videoRef} className="hidden" playsInline muted />
                  <canvas ref={canvasRef} width={540} height={405} className="h-full w-full -scale-x-100" />
                  {!ready && !error && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300">
                      <CamIcon className="animate-pulse" size={32} />
                      <p className="mt-3 text-sm">Loading Google gesture model…</p>
                    </div>
                  )}
                  {error && (
                    <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-amber-200">{error}</div>
                  )}
                  {live && (
                    <div className="absolute left-3 top-3 rounded-full bg-emerald-600 px-4 py-2 text-base font-bold text-white shadow-lg">
                      {live.label} {live.sub && <span className="text-white/80 text-sm">· {live.sub}</span>}
                    </div>
                  )}
                  {live && (
                    <div className="absolute bottom-3 left-3 right-3">
                      <div className="h-2 overflow-hidden rounded-full bg-white/30">
                        <div className="h-full bg-emerald-400 transition-all" style={{ width: `${Math.min(100, (hold / (mode === "gesture" ? HOLD_GESTURE : HOLD_LETTER)) * 100)}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-white/80">{mode === "gesture" ? "Hold the gesture to add it…" : "Hold to add the letter · fist = space"}</p>
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                  <span className="text-moei-muted">Google MediaPipe (pretrained) · runs locally, no video leaves device</span>
                  <span className="font-semibold text-emerald-700">{status}</span>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-moei-line bg-white p-4">
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                  <Keyboard size={13} /> Type your message
                </div>
                <form onSubmit={(e) => { e.preventDefault(); const v = typed; setTyped(""); send(v); }} className="flex gap-2">
                  <input
                    value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus
                    placeholder={language === "ar" ? "اكتب رسالتك…" : "Type your message…"}
                    dir={language === "ar" ? "rtl" : "ltr"}
                    className="flex-1 rounded-lg border border-moei-line bg-white px-3 py-3 text-sm outline-none focus:border-moei-bronze"
                  />
                  <button type="submit" disabled={busy || !typed.trim()} className="moei-btn-primary justify-center disabled:opacity-50">
                    <Send size={14} /> Send
                  </button>
                </form>
                <p className="mt-2 text-[11px] text-moei-muted">Text always works — no camera needed. Great fallback if signing is hard to see.</p>
              </div>
            )}

            {/* draft / message being built (gesture + spell) */}
            {mode !== "type" && (
              <div className="rounded-2xl border border-moei-line bg-white p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Your message</span>
                  <button onClick={() => { setTokens([]); setLetters([]); }} className="text-moei-muted hover:text-red-600" aria-label="Clear"><Trash2 size={14} /></button>
                </div>
                <div className="min-h-[52px] rounded-lg border border-moei-line bg-moei-cream/30 px-3 py-2 flex flex-wrap gap-2 items-center" dir={language === "ar" ? "rtl" : "ltr"}>
                  {draftText.length ? draftText.map((w, i) => (
                    <span key={i} className={`rounded-full px-3 py-1 text-sm font-semibold ${i === tokens.length && letters.length ? "bg-emerald-100 border border-emerald-300 text-emerald-800" : "bg-moei-bronze/10 border border-moei-bronze/30 text-moei-ink"}`}>
                      {w}
                    </span>
                  )) : <span className="text-moei-muted text-sm">{mode === "gesture" ? "Gesture to build your message — pause 2.5s to send." : "Fingerspell letters · fist = space · then Send."}</span>}
                </div>
                <button onClick={sendCurrent} disabled={busy || draftText.length === 0} className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50">
                  <Send size={14} /> {busy ? "Sending…" : mode === "gesture" ? "Send now (or pause to auto-send)" : "Send"}
                </button>
              </div>
            )}
          </div>

          {/* right: contextual help (dictionary / chart / tips) + conversation */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Hand size={13} /> {mode === "gesture" ? "Gesture dictionary" : mode === "spell" ? "Fingerspelling chart" : "Tips"}
              </div>

              {mode === "gesture" && (
                <div className="grid grid-cols-1 gap-1.5">
                  {GESTURES.map((g) => (
                    <div key={g.key} className="flex items-center gap-3 rounded-lg border border-moei-line px-3 py-2">
                      <span className="text-2xl">{g.emoji}</span>
                      <div className="min-w-0">
                        <div className="text-[13px] font-semibold text-moei-ink truncate">{g[language]}</div>
                        <div className="text-[11px] text-moei-muted truncate">{language === "en" ? g.ar : g.en}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {mode === "spell" && (
                <div className="grid grid-cols-2 gap-1.5 max-h-[300px] overflow-y-auto">
                  {ALPHABET.map((a) => (
                    <div key={a.pattern} className="flex items-center gap-2 rounded-lg border border-moei-line px-2 py-1.5">
                      <span className="text-sm font-bold text-moei-bronze w-6 text-center">{language === "en" ? a.en : a.ar}</span>
                      <FingerDots pattern={a.pattern} />
                    </div>
                  ))}
                </div>
              )}

              {mode === "type" && (
                <p className="text-[12px] text-moei-body leading-relaxed">
                  Just type and press Send. This mode needs no camera and is the most reliable for noisy
                  rooms or poor lighting. The assistant keeps the same conversation across all modes.
                </p>
              )}

              <div className="mt-3 rounded-lg bg-moei-cream/40 p-2.5 text-[11px] text-moei-body leading-relaxed">
                <strong>For judges:</strong> {mode === "gesture"
                  ? "Make any gesture (hold ½s) — it adds the phrase. Chain a few, pause, the assistant replies with voice. No training — Google's pretrained model."
                  : mode === "spell"
                  ? "Raise the fingers shown for a letter (filled dot = finger up), hold ½s. Make a fist for a space. Then Send."
                  : "Type anything — always works."} Use the <strong>{language === "en" ? "العربية" : "English"}</strong> toggle for the other language.
              </div>
            </div>

            {/* conversation */}
            <div className="rounded-2xl border border-moei-line bg-white p-4 flex flex-col">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-moei-line">
                <MessageCircle size={16} className="text-moei-bronze" />
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Conversation</span>
              </div>
              <div className="space-y-3 max-h-[300px] overflow-y-auto">
                {messages.length === 0 ? (
                  <p className="text-xs text-moei-muted text-center py-6">Gesture, spell, or type to start…</p>
                ) : messages.map((m, i) => (
                  <div key={i} className={`text-xs p-2.5 rounded-lg ${m.role === "user" ? "bg-moei-bronze/10 border border-moei-bronze/30 text-moei-ink" : "bg-emerald-50 border border-emerald-200 text-emerald-900"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-[10px]">{m.role === "user" ? "You" : "Assistant"}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] text-moei-muted">{m.time}</span>
                        {m.role === "assistant" && (
                          <button onClick={() => speak(m.text, language)} className="text-emerald-700 hover:text-emerald-900" aria-label="Read aloud"><Volume2 size={12} /></button>
                        )}
                      </div>
                    </div>
                    <p className="text-[11px] leading-relaxed whitespace-pre-line">{m.text}</p>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// Small 5-dot finger indicator [thumb,index,middle,ring,pinky] — filled = raise that finger.
function FingerDots({ pattern }: { pattern: string }) {
  return (
    <div className="flex items-center gap-0.5">
      {pattern.split("").map((b, i) => (
        <span key={i} className={`h-2.5 w-2.5 rounded-full border ${b === "1" ? "bg-moei-bronze border-moei-bronze" : "bg-transparent border-moei-line"}`} />
      ))}
    </div>
  );
}
