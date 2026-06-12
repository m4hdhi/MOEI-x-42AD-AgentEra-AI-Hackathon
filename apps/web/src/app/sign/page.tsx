"use client";

/**
 * Digital Human — Multi-modal Sign-Language studio with continuous, voice-enabled chat.
 *
 * ONE camera + ONE pretrained model (Google MediaPipe Gesture Recognizer, tasks-vision) powers
 * THREE sign-detection modes the user picks between:
 *   1) Gestures   — 7 pretrained gestures → MOEI phrases (zero training, instant).
 *   2) Word signs — hand-shape (finger pattern) → a whole MOEI word (zero setup, chart shown).
 *   3) Fingerspell — finger pattern → letter (A–Z / Arabic), builds words; fist = space.
 *
 * The recognizer returns BOTH `gestures` and `landmarks`, so all three modes share one model.
 * Everything feeds ONE continuous, context-aware conversation with voice output. EN + AR toggle.
 * A small text box stays as a safety fallback. Fully client-side; video never leaves the device.
 *   Model: ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer
 */

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import {
  Send, Trash2, Volume2, Camera as CamIcon, RotateCcw, MessageCircle, Hand,
  Sparkles, SpellCheck, Hand as HandIcon, Keyboard,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// ── Mode 1: pretrained-gesture → MOEI phrase (bilingual + emoji) ──
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

// ── Mode 2: finger-pattern → whole MOEI word. Deterministic; finger chart shown. ──
// pattern = [thumb,index,middle,ring,pinky] up/down.
type Sign = { pattern: string; en: string; ar: string };
const WORD_SIGNS: Sign[] = [
  { pattern: "11111", en: "Hello",              ar: "مرحبا" },
  { pattern: "00000", en: "Yes",                ar: "نعم" },
  { pattern: "00001", en: "No",                 ar: "لا" },
  { pattern: "10000", en: "Thank you",          ar: "شكرا" },
  { pattern: "01000", en: "I need help",        ar: "أحتاج مساعدة" },
  { pattern: "01100", en: "Check my status",    ar: "حالة طلبي" },
  { pattern: "01110", en: "Housing",            ar: "السكن" },
  { pattern: "11000", en: "I have a complaint", ar: "لدي شكوى" },
  { pattern: "00011", en: "Electricity",        ar: "الكهرباء" },
  { pattern: "10001", en: "Emergency",          ar: "طوارئ" },
];
const WORD_BY_PATTERN = Object.fromEntries(WORD_SIGNS.map((s) => [s.pattern, s]));

// ── Mode 3: finger-pattern → letter. "00000" (fist) = space/commit word. ──
const EN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const AR_LETTERS = "ا ب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه و ي".split(" ");
const ALPHABET: { pattern: string; en: string; ar: string }[] = AR_LETTERS.map((ar, i) => ({
  pattern: (i + 1).toString(2).padStart(5, "0"), // 1.."11100" — 00000 reserved for space
  en: EN_LETTERS[i] || "",
  ar,
}));
const LETTER_BY_PATTERN = Object.fromEntries(ALPHABET.map((a) => [a.pattern, a]));

const HOLD = 10;           // frames to commit a gesture/word (~0.5s)
const HOLD_LETTER = 8;     // frames to commit a letter
const SPACE_FRAMES = 6;    // fist frames to commit a spelled word
const AUTOSEND_MS = 2500;  // pause auto-sends (gesture / word modes)
const MIN_SCORE = 0.5;

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const ESM = "https://esm.sh/@mediapipe/tasks-vision@0.10.18";

type Mode = "gesture" | "word" | "spell";
type ChatMsg = { role: "user" | "assistant"; text: string; time: string; channel?: string };

export default function SignPage() {
  return (
    <LoginGate
      title="Sign-Language Assistant"
      subtitle="Three sign-detection modes, one continuous voice chat. Sign in with UAE PASS."
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
  const [status, setStatus] = useState("Starting camera…");
  const [live, setLive] = useState<{ label: string; sub: string } | null>(null);
  const [hold, setHold] = useState(0);
  const [tokens, setTokens] = useState<string[]>([]);   // committed words/phrases (display text)
  const [letters, setLetters] = useState<string[]>([]); // current word being spelled
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState("");
  const [showType, setShowType] = useState(false);
  const [sessionId] = useState(() => "sign-" + (session.emirates_id || "anon") + "-" + Date.now());

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

  useEffect(() => {
    fetch(`${API_URL}/chat/history?n=20`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const turns: ChatMsg[] = (d.turns || []).map((t: any) => ({
          role: t.role,
          text: t.text,
          channel: t.channel,
          time: t.channel ? t.channel.toUpperCase() : "History",
        }));
        if (turns.length) setMessages(turns);
      })
      .catch(() => {});
  }, []);

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
          channel: "sign", session_id: sessionId, language: lang, text: t,
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

  // pause → auto-send (gesture + word modes; spell uses the Send button)
  useEffect(() => {
    const id = setInterval(() => {
      const m = modeRef.current;
      if ((m === "gesture" || m === "word") && tokensRef.current.length > 0 && !busyRef.current && Date.now() - lastAtRef.current > AUTOSEND_MS) {
        sendCurrent();
      }
    }, 400);
    return () => clearInterval(id);
  }, [sendCurrent]);

  // MediaPipe pretrained recognizer loop (gestures + landmarks)
  useEffect(() => {
    let recognizer: any, stream: MediaStream | null = null, raf = 0, cancelled = false;
    let lastVideoTime = -1;
    let gKey = "", gHold = 0, gCommitted = false;       // gesture
    let wPat = "", wHold = 0, wCommitted = false;        // word sign
    let lPat = "", lHold = 0, lCommitted = false, fistFrames = 0; // letter

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
        setError("We couldn't start your camera. Please allow camera access (Chrome or Edge work best) — or type your message instead.");
        setStatus("Camera unavailable — type instead");
        setShowType(true);
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

            const m = modeRef.current, lang = langRef.current;

            if (m === "gesture") {
              const g = res?.gestures?.[0]?.[0];
              const key = g?.categoryName, score = g?.score ?? 0;
              if (key && key !== "None" && key !== "Unknown" && GESTURE_BY_KEY[key] && score >= MIN_SCORE) {
                const gi = GESTURE_BY_KEY[key];
                setLive({ label: `${gi.emoji} ${gi[lang]}`, sub: `${Math.round(score * 100)}%` });
                if (key === gKey) {
                  gHold++; setHold(gHold);
                  if (gHold >= HOLD && !gCommitted) {
                    gCommitted = true; setTokens((t) => [...t, gi[lang]]);
                    lastAtRef.current = Date.now(); setStatus(`Added: ${gi.en}`);
                  }
                } else { gKey = key; gHold = 0; gCommitted = false; setHold(0); }
              } else { setLive(null); gKey = ""; gHold = 0; gCommitted = false; setHold(0); }

            } else if (m === "word") {
              if (lms) {
                const pat = fingersUp(lms);
                const s = WORD_BY_PATTERN[pat];
                if (s) {
                  setLive({ label: s[lang], sub: pat });
                  if (pat === wPat) {
                    wHold++; setHold(wHold);
                    if (wHold >= HOLD && !wCommitted) {
                      wCommitted = true; setTokens((t) => [...t, s[lang]]);
                      lastAtRef.current = Date.now(); setStatus(`Added: ${s.en}`);
                    }
                  } else { wPat = pat; wHold = 0; wCommitted = false; setHold(0); }
                } else { setLive(null); wPat = ""; wHold = 0; wCommitted = false; setHold(0); }
              } else { setLive(null); wPat = ""; wHold = 0; wCommitted = false; setHold(0); }

            } else if (m === "spell") {
              if (lms) {
                const pat = fingersUp(lms);
                if (pat === "00000") {
                  fistFrames++;
                  setLive({ label: "✊ space", sub: "commit word" });
                  if (fistFrames >= SPACE_FRAMES) {
                    if (lettersRef.current.length) {
                      const w = lettersRef.current.join("");
                      setTokens((t) => [...t, w]); setLetters([]);
                      lastAtRef.current = Date.now(); setStatus(`Word: ${w}`);
                    }
                    fistFrames = -999;
                  }
                  lPat = ""; lHold = 0; lCommitted = false; setHold(0);
                } else {
                  fistFrames = 0;
                  const entry = LETTER_BY_PATTERN[pat];
                  const ch = entry ? entry[lang] : "";
                  if (ch) {
                    setLive({ label: ch, sub: pat });
                    if (pat === lPat) {
                      lHold++; setHold(lHold);
                      if (lHold >= HOLD_LETTER && !lCommitted) {
                        lCommitted = true; setLetters((l) => [...l, ch]); setStatus(`Letter: ${ch}`);
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
  const holdMax = mode === "spell" ? HOLD_LETTER : HOLD;

  return (
    <div className="bg-moei-cream/30 min-h-screen flex flex-col">
      {/* header */}
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="moei-kicker">Accessibility · Sign Language</span>
              <h1 className="mt-1 moei-h-section">Sign Language Assistant</h1>
              <p className="mt-1 max-w-2xl text-sm text-moei-body">
                Three ways to sign — quick gestures, whole-word signs, or fingerspelling — all in one
                continuous conversation that replies in text and voice. English and Arabic.
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

          {/* mode selector — three sign-detection tabs */}
          <div className="mt-4 inline-flex flex-wrap rounded-xl border border-moei-line bg-moei-cream/40 p-1">
            {([
              { k: "gesture", icon: Sparkles, label: "Gestures", hint: "instant" },
              { k: "word", icon: HandIcon, label: "Word signs", hint: "sign → word" },
              { k: "spell", icon: SpellCheck, label: "Fingerspell", hint: "sign → letters" },
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
          {/* left: camera + draft */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="relative overflow-hidden rounded-xl bg-slate-900" style={{ aspectRatio: "4/3" }}>
                <video ref={videoRef} className="hidden" playsInline muted />
                <canvas ref={canvasRef} width={540} height={405} className="h-full w-full -scale-x-100" />
                {!ready && !error && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300">
                    <CamIcon className="animate-pulse" size={32} />
                    <p className="mt-3 text-sm">Starting your camera…</p>
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
                      <div className="h-full bg-emerald-400 transition-all" style={{ width: `${Math.min(100, (hold / holdMax) * 100)}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-white/80">
                      {mode === "gesture" ? "Hold the gesture to add it…" : mode === "word" ? "Hold the sign to add the word…" : "Hold to add the letter · fist = space"}
                    </p>
                  </div>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-moei-muted">Runs privately on your device — your camera never leaves it.</span>
                <span className="font-semibold text-emerald-700">{status}</span>
              </div>
            </div>

            {/* draft / message being built */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Your message</span>
                <div className="flex items-center gap-3">
                  <button onClick={() => setShowType((v) => !v)} className="text-moei-muted hover:text-moei-bronze" title="Type instead (fallback)"><Keyboard size={14} /></button>
                  <button onClick={() => { setTokens([]); setLetters([]); }} className="text-moei-muted hover:text-red-600" aria-label="Clear"><Trash2 size={14} /></button>
                </div>
              </div>
              <div className="min-h-[52px] rounded-lg border border-moei-line bg-moei-cream/30 px-3 py-2 flex flex-wrap gap-2 items-center" dir={language === "ar" ? "rtl" : "ltr"}>
                {draftText.length ? draftText.map((w, i) => (
                  <span key={i} className={`rounded-full px-3 py-1 text-sm font-semibold ${i === tokens.length && letters.length ? "bg-emerald-100 border border-emerald-300 text-emerald-800" : "bg-moei-bronze/10 border border-moei-bronze/30 text-moei-ink"}`}>
                    {w}
                  </span>
                )) : <span className="text-moei-muted text-sm">{mode === "spell" ? "Fingerspell letters · fist = space · then Send." : "Sign to build your message — pause 2.5s to send."}</span>}
              </div>
              <button onClick={sendCurrent} disabled={busy || draftText.length === 0} className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50">
                <Send size={14} /> {busy ? "Sending…" : mode === "spell" ? "Send" : "Send now (or pause to auto-send)"}
              </button>

              {/* discreet text fallback */}
              {showType && (
                <form onSubmit={(e) => { e.preventDefault(); const v = typed; setTyped(""); send(v); }} className="mt-3 flex gap-2 border-t border-moei-line pt-3">
                  <input
                    value={typed} onChange={(e) => setTyped(e.target.value)}
                    placeholder={language === "ar" ? "أو اكتب…" : "Or type…"}
                    dir={language === "ar" ? "rtl" : "ltr"}
                    className="flex-1 rounded-lg border border-moei-line bg-white px-3 py-2 text-sm outline-none focus:border-moei-bronze"
                  />
                  <button type="submit" disabled={busy || !typed.trim()} className="moei-btn-secondary disabled:opacity-50"><Send size={14} /></button>
                </form>
              )}
            </div>
          </div>

          {/* right: contextual chart + conversation */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Hand size={13} /> {mode === "gesture" ? "Gesture dictionary" : mode === "word" ? "Word-sign chart" : "Fingerspelling chart"}
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

              {mode === "word" && (
                <div className="grid grid-cols-1 gap-1.5 max-h-[300px] overflow-y-auto">
                  {WORD_SIGNS.map((s) => (
                    <div key={s.pattern} className="flex items-center justify-between gap-2 rounded-lg border border-moei-line px-3 py-2">
                      <div className="min-w-0">
                        <div className="text-[13px] font-semibold text-moei-ink truncate">{s[language]}</div>
                        <div className="text-[11px] text-moei-muted truncate">{language === "en" ? s.ar : s.en}</div>
                      </div>
                      <FingerDots pattern={s.pattern} />
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

              <div className="mt-3 rounded-lg bg-moei-cream/40 p-2.5 text-[11px] text-moei-body leading-relaxed">
                <strong>How to use:</strong> {mode === "gesture"
                  ? "Make any gesture and hold it briefly — it adds the phrase. Chain a few, pause, and the assistant replies in text and voice."
                  : mode === "word"
                  ? "Raise the fingers shown (filled dot = finger up) and hold briefly — it adds the whole word. Pause to send."
                  : "Raise the fingers shown for a letter and hold briefly. Make a fist for a space, then Send."} Use the <strong>{language === "en" ? "العربية" : "English"}</strong> toggle for the other language.
              </div>
            </div>

            {/* conversation */}
            <div className="rounded-2xl border border-moei-line bg-white p-4 flex flex-col">
              <div className="mb-3 flex items-center justify-between gap-2 border-b border-moei-line pb-3">
                <div className="flex items-center gap-2">
                  <MessageCircle size={16} className="text-moei-bronze" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Conversation history</span>
                </div>
                <Link href="/chat" className="text-[11px] font-semibold text-moei-bronze hover:text-moei-ink">
                  Open full chat
                </Link>
              </div>
              <div className="space-y-3 max-h-[300px] overflow-y-auto">
                {messages.length === 0 ? (
                  <p className="text-xs text-moei-muted text-center py-6">Sign or type to start the conversation…</p>
                ) : messages.map((m, i) => (
                  <div key={i} className={`text-xs p-2.5 rounded-lg ${m.role === "user" ? "bg-moei-bronze/10 border border-moei-bronze/30 text-moei-ink" : "bg-emerald-50 border border-emerald-200 text-emerald-900"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-[10px]">{m.role === "user" ? "You" : "Assistant"}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] uppercase text-moei-muted">{m.channel ?? m.time}</span>
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

// 5-dot finger indicator [thumb,index,middle,ring,pinky] — filled = raise that finger.
function FingerDots({ pattern }: { pattern: string }) {
  return (
    <div className="flex items-center gap-0.5 shrink-0" title="thumb · index · middle · ring · pinky">
      {pattern.split("").map((b, i) => (
        <span key={i} className={`h-2.5 w-2.5 rounded-full border ${b === "1" ? "bg-moei-bronze border-moei-bronze" : "bg-transparent border-moei-line"}`} />
      ))}
    </div>
  );
}
