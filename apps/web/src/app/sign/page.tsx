"use client";

/**
 * Digital Human — Sign-Language / gesture input with continuous, voice-enabled chat.
 *
 * Uses Google's PRETRAINED MediaPipe Gesture Recognizer (tasks-vision) — a model trained by
 * Google that recognises 7 hand gestures in-browser with ZERO setup/training:
 *   Closed_Fist, Open_Palm, Pointing_Up, Thumb_Up, Thumb_Down, Victory, ILoveYou
 *   (https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer)
 *
 * We map each gesture → a MOEI service phrase (English + Arabic), let them accumulate into a
 * sentence (pause auto-sends), and keep a continuous, context-aware conversation with voice
 * output. A text-input fallback guarantees the demo works even without a camera. Runs fully
 * client-side; video never leaves the device.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Send, Trash2, Volume2, Camera as CamIcon, RotateCcw, MessageCircle, Hand, Keyboard,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// Pretrained-gesture → MOEI phrase dictionary (bilingual). These ARE the samples for judges.
type Gesture = { key: string; emoji: string; en: string; ar: string };
const GESTURES: Gesture[] = [
  { key: "Open_Palm",    emoji: "🖐️", en: "Hello",              ar: "مرحبا" },
  { key: "Thumb_Up",     emoji: "👍", en: "Yes",                ar: "نعم" },
  { key: "Thumb_Down",   emoji: "👎", en: "No",                 ar: "لا" },
  { key: "Pointing_Up",  emoji: "☝️", en: "I need help",        ar: "أحتاج مساعدة" },
  { key: "Victory",      emoji: "✌️", en: "Check my status",    ar: "حالة طلبي" },
  { key: "Closed_Fist",  emoji: "✊", en: "I have a complaint", ar: "لدي شكوى" },
  { key: "ILoveYou",     emoji: "🤟", en: "Thank you",          ar: "شكرا" },
];
const GESTURE_BY_KEY = Object.fromEntries(GESTURES.map((g) => [g.key, g]));

const HOLD_FRAMES = 10;        // ~0.5s of a stable gesture to commit it
const AUTOSEND_MS = 2500;      // pause after last word → send the sentence
const MIN_SCORE = 0.55;        // confidence floor for a gesture

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const ESM = "https://esm.sh/@mediapipe/tasks-vision@0.10.18";

type ChatMsg = { role: "user" | "assistant"; text: string; time: string };

export default function SignPage() {
  return (
    <LoginGate
      title="Sign-Language Assistant"
      subtitle="Pretrained gesture recognition (no setup) with continuous, voice chat. Sign in with UAE PASS."
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
  const [status, setStatus] = useState("Loading gesture model…");
  const [live, setLive] = useState<{ key: string; score: number } | null>(null);
  const [hold, setHold] = useState(0);
  const [sentence, setSentence] = useState<string[]>([]); // gesture keys
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState("");
  const [sessionId] = useState(() => "sign-" + (session.emirates_id || "anon") + "-" + Date.now());

  // refs for the rAF loop / async send
  const sentenceRef = useRef<string[]>([]);
  const lastWordAtRef = useRef(Date.now());
  const busyRef = useRef(false);
  const langRef = useRef(language);
  useEffect(() => { sentenceRef.current = sentence; }, [sentence]);
  useEffect(() => { busyRef.current = busy; }, [busy]);
  useEffect(() => { langRef.current = language; }, [language]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ── send a sentence (gestures or typed text) to the assistant, continuous session ──
  const send = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || busyRef.current) return;
    const lang = langRef.current;
    setBusy(true);
    setSentence([]);
    lastWordAtRef.current = Date.now();
    setMessages((m) => [...m, { role: "user", text: t, time: new Date().toLocaleTimeString() }]);
    try {
      const r = await fetch(`${API_URL}/chat/web`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: session.emirates_id || "anonymous",
          channel: "web",
          session_id: sessionId,
          language: lang,
          text: t,
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

  const sendSentence = useCallback(() => {
    const lang = langRef.current;
    const text = sentenceRef.current.map((k) => GESTURE_BY_KEY[k]?.[lang] || k).join(" ");
    send(text);
  }, [send]);

  function speak(text: string, lang: "en" | "ar") {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang === "ar" || /[؀-ۿ]/.test(text) ? "ar-AE" : "en-US";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }
  }

  // ── pause → auto-send accumulated gestures ──
  useEffect(() => {
    const id = setInterval(() => {
      if (sentenceRef.current.length > 0 && !busyRef.current && Date.now() - lastWordAtRef.current > AUTOSEND_MS) {
        sendSentence();
      }
    }, 400);
    return () => clearInterval(id);
  }, [sendSentence]);

  // ── MediaPipe pretrained Gesture Recognizer loop ──
  useEffect(() => {
    let recognizer: any, stream: MediaStream | null = null, raf = 0, cancelled = false;
    let lastVideoTime = -1;
    let lastKey = "";
    let holdCount = 0;
    let committed = false;

    async function init() {
      try {
        // dynamic ESM import that webpack won't try to bundle
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
        setStatus("Ready — make a gesture from the dictionary");
        loop();
      } catch (e) {
        setError("Could not load the gesture model or camera. Allow camera access and use Chrome/Edge — or use the text box below.");
        setStatus("Camera unavailable — type instead");
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
            // draw landmarks
            const lms = res?.landmarks?.[0];
            if (lms) {
              ctx.fillStyle = "#9c8853";
              for (const p of lms) { ctx.beginPath(); ctx.arc(p.x * cv.width, p.y * cv.height, 3, 0, 6.28); ctx.fill(); }
            }
            const g = res?.gestures?.[0]?.[0];
            const key = g?.categoryName;
            const score = g?.score ?? 0;
            if (key && key !== "None" && key !== "Unknown" && GESTURE_BY_KEY[key] && score >= MIN_SCORE) {
              setLive({ key, score });
              if (key === lastKey) {
                holdCount++;
                setHold(holdCount);
                if (holdCount >= HOLD_FRAMES && !committed) {
                  committed = true;
                  setSentence((s) => [...s, key]);
                  lastWordAtRef.current = Date.now();
                  setStatus(`Recognised: ${GESTURE_BY_KEY[key].en}`);
                }
              } else {
                lastKey = key; holdCount = 0; committed = false; setHold(0);
              }
            } else {
              setLive(null); lastKey = ""; holdCount = 0; committed = false; setHold(0);
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

  return (
    <div className="bg-moei-cream/30 min-h-screen flex flex-col">
      {/* header */}
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="moei-kicker">Accessibility · Digital Human</span>
              <h1 className="mt-1 moei-h-section">Sign-Language Conversation</h1>
              <p className="mt-1 max-w-2xl text-sm text-moei-body">
                Google&apos;s pretrained gesture model recognises your hand signs instantly — no setup. Each
                gesture is a phrase; they build a sentence and the assistant replies with voice. English + Arabic.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setLanguage(language === "en" ? "ar" : "en")} className="moei-btn-secondary">
                {language === "en" ? "العربية" : "English"}
              </button>
              <button onClick={() => { setMessages([]); setSentence([]); }} className="moei-btn-secondary">
                <RotateCcw size={14} /> Clear chat
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="flex-1 mx-auto max-w-7xl px-6 py-6 w-full">
        <div className="grid gap-6 lg:grid-cols-3">
          {/* camera + input */}
          <div className="lg:col-span-2 space-y-4">
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
                    {GESTURE_BY_KEY[live.key]?.emoji} {GESTURE_BY_KEY[live.key]?.[language]} · {Math.round(live.score * 100)}%
                  </div>
                )}
                {live && (
                  <div className="absolute bottom-3 left-3 right-3">
                    <div className="h-2 overflow-hidden rounded-full bg-white/30">
                      <div className="h-full bg-emerald-400 transition-all" style={{ width: `${Math.min(100, (hold / HOLD_FRAMES) * 100)}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-white/80">Hold the gesture to add it…</p>
                  </div>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-moei-muted">Google MediaPipe Gesture Recognizer (pretrained) · runs locally, no video leaves device</span>
                <span className="font-semibold text-emerald-700">{status}</span>
              </div>
            </div>

            {/* sentence being built */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Your message</span>
                <button onClick={() => setSentence([])} className="text-moei-muted hover:text-red-600" aria-label="Clear"><Trash2 size={14} /></button>
              </div>
              <div className="min-h-[52px] rounded-lg border border-moei-line bg-moei-cream/30 px-3 py-2 flex flex-wrap gap-2 items-center" dir={language === "ar" ? "rtl" : "ltr"}>
                {sentence.length ? sentence.map((k, i) => (
                  <span key={i} className="rounded-full bg-moei-bronze/10 border border-moei-bronze/30 px-3 py-1 text-sm font-semibold text-moei-ink">
                    {GESTURE_BY_KEY[k]?.emoji} {GESTURE_BY_KEY[k]?.[language]}
                  </span>
                )) : <span className="text-moei-muted text-sm">Gesture to build your message — pause 2.5s to send.</span>}
              </div>
              <button onClick={sendSentence} disabled={busy || sentence.length === 0} className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50">
                <Send size={14} /> {busy ? "Sending…" : "Send now (or pause to auto-send)"}
              </button>
            </div>

            {/* text fallback — always works */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Keyboard size={13} /> Or type instead
              </div>
              <form
                onSubmit={(e) => { e.preventDefault(); const v = typed; setTyped(""); send(v); }}
                className="flex gap-2"
              >
                <input
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={language === "ar" ? "اكتب رسالتك…" : "Type your message…"}
                  dir={language === "ar" ? "rtl" : "ltr"}
                  className="flex-1 rounded-lg border border-moei-line bg-white px-3 py-2 text-sm outline-none focus:border-moei-bronze"
                />
                <button type="submit" disabled={busy || !typed.trim()} className="moei-btn-primary justify-center disabled:opacity-50">
                  <Send size={14} />
                </button>
              </form>
            </div>
          </div>

          {/* right column */}
          <div className="space-y-4">
            {/* gesture dictionary — samples for judges */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Hand size={13} /> Gesture dictionary
              </div>
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
              <div className="mt-3 rounded-lg bg-moei-cream/40 p-2.5 text-[11px] text-moei-body leading-relaxed">
                <strong>For judges:</strong> Make any gesture above (hold ~½s) — it adds the phrase. Chain a few,
                pause 2.5s, the assistant replies with voice. No training needed — it&apos;s Google&apos;s pretrained
                model. Switch the <strong>{language === "en" ? "العربية" : "English"}</strong> toggle for Arabic.
              </div>
            </div>

            {/* conversation */}
            <div className="rounded-2xl border border-moei-line bg-white p-4 flex flex-col">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-moei-line">
                <MessageCircle size={16} className="text-moei-bronze" />
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Conversation</span>
              </div>
              <div className="space-y-3 max-h-[340px] overflow-y-auto">
                {messages.length === 0 ? (
                  <p className="text-xs text-moei-muted text-center py-6">Gesture or type to start the conversation…</p>
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
