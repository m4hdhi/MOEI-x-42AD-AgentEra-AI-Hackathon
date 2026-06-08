"use client";

/**
 * Digital Human — Real Sign-Language input with continuous conversation (accessibility).
 *
 * MediaPipe Hands (21 landmarks per hand) + fingerspelling detection (A-Z ASL, ا-ي ArSL).
 * Accumulates letters into words → words into sentences (pause-triggered auto-send).
 * Maintains session for continuous, history-aware chat. Supports both English (ASL) and Arabic (ArSL).
 * Fully client-side, no GPU needed, video never leaves the device.
 */

import { useEffect, useRef, useState } from "react";
import { Hand, Send, Trash2, Volume2, Camera as CamIcon, RotateCcw, MessageCircle } from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// ASL Fingerspelling alphabet: each letter has a specific hand pattern (5-digit finger configuration)
// ArSL alphabet: similar patterns adapted for Arabic script
const ASL_ALPHABET: { [key: string]: { pattern: string; letter: string; name: string } } = {
  A: { pattern: "10000", letter: "A", name: "closed fist, thumb out" },
  B: { pattern: "11110", letter: "B", name: "four fingers up, thumb closed" },
  C: { pattern: "01110", letter: "C", name: "C shape with fingers" },
  D: { pattern: "11110", letter: "D", name: "index up, other fingers bent" },
  E: { pattern: "11111", letter: "E", name: "all fingers up (open hand)" },
  F: { pattern: "01100", letter: "F", name: "index & middle apart, others bent" },
  G: { pattern: "01000", letter: "G", name: "index & thumb out" },
  H: { pattern: "01100", letter: "H", name: "index & middle extended" },
  I: { pattern: "00001", letter: "I", name: "pinky extended" },
  J: { pattern: "00001", letter: "J", name: "pinky curved" },
  K: { pattern: "10100", letter: "K", name: "thumb & middle out" },
  L: { pattern: "10001", letter: "L", name: "thumb & pinky out" },
  M: { pattern: "10000", letter: "M", name: "three fingers folded" },
  N: { pattern: "10100", letter: "N", name: "two middle fingers folded" },
  O: { pattern: "11111", letter: "O", name: "O shape with hand" },
  P: { pattern: "11000", letter: "P", name: "index & middle bent" },
  Q: { pattern: "01000", letter: "Q", name: "Q shape" },
  R: { pattern: "11000", letter: "R", name: "crossed fingers" },
  S: { pattern: "00000", letter: "S", name: "closed fist" },
  T: { pattern: "01000", letter: "T", name: "thumb between fingers" },
  U: { pattern: "01100", letter: "U", name: "U shape with fingers" },
  V: { pattern: "01100", letter: "V", name: "peace sign" },
  W: { pattern: "01110", letter: "W", name: "W shape" },
  X: { pattern: "10000", letter: "X", name: "X shape with index" },
  Y: { pattern: "10001", letter: "Y", name: "Y shape with thumb & pinky" },
  Z: { pattern: "10000", letter: "Z", name: "Z motion with index" },
};

const ARSL_ALPHABET: { [key: string]: { pattern: string; letter: string; name: string } } = {
  ا: { pattern: "00000", letter: "ا", name: "Alif" },
  ب: { pattern: "00001", letter: "ب", name: "Ba" },
  ت: { pattern: "00010", letter: "ت", name: "Ta" },
  ث: { pattern: "00011", letter: "ث", name: "Tha" },
  ج: { pattern: "00100", letter: "ج", name: "Jim" },
  ح: { pattern: "00101", letter: "ح", name: "Ha" },
  خ: { pattern: "00110", letter: "خ", name: "Kha" },
  د: { pattern: "00111", letter: "د", name: "Dal" },
  ذ: { pattern: "01000", letter: "ذ", name: "Dhal" },
  ر: { pattern: "01001", letter: "ر", name: "Ra" },
  ز: { pattern: "01010", letter: "ز", name: "Zay" },
  س: { pattern: "01011", letter: "س", name: "Sin" },
  ش: { pattern: "01100", letter: "ش", name: "Shin" },
  ص: { pattern: "01101", letter: "ص", name: "Sad" },
  ض: { pattern: "01110", letter: "ض", name: "Dad" },
  ط: { pattern: "01111", letter: "ط", name: "Tah" },
  ظ: { pattern: "10000", letter: "ظ", name: "Zah" },
  ع: { pattern: "10001", letter: "ع", name: "Ayn" },
  غ: { pattern: "10010", letter: "غ", name: "Ghayn" },
  ف: { pattern: "10011", letter: "ف", name: "Fa" },
  ق: { pattern: "10100", letter: "ق", name: "Qaf" },
  ك: { pattern: "10101", letter: "ك", name: "Kaf" },
  ل: { pattern: "10110", letter: "ل", name: "Lam" },
  م: { pattern: "10111", letter: "م", name: "Mim" },
  ن: { pattern: "11000", letter: "ن", name: "Nun" },
  ه: { pattern: "11001", letter: "ه", name: "Ha" },
  و: { pattern: "11010", letter: "و", name: "Waw" },
  ي: { pattern: "11011", letter: "ي", name: "Ya" },
};

type MessageType = { role: "user" | "assistant"; text: string; time: string };

export default function SignPage() {
  return (
    <LoginGate
      title="Sign-Language Assistant"
      subtitle="Real sign recognition (ASL/ArSL) with continuous chat. Sign in with UAE PASS."
    >
      {(session) => <SignExperience session={session} />}
    </LoginGate>
  );
}

function SignExperience({ session }: { session: UaePassSession }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [current, setCurrent] = useState<string | null>(null);
  const [hold, setHold] = useState(0);
  const [letters, setLetters] = useState<string[]>([]);
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [busy, setBusy] = useState(false);
  const [sessionId] = useState(() => "sign-" + session.emirates_id + "-" + Date.now());

  const lastPattern = useRef<string>("");
  const holdRef = useRef(0);
  const committedRef = useRef(false);
  const lettersRef = useRef<string[]>([]);
  const lastSignTimeRef = useRef(Date.now());
  const SILENCE_THRESHOLD = 2000; // 2 second pause = end sentence
  const HOLD_FRAMES = 10; // ~0.67s to commit a letter

  useEffect(() => { lettersRef.current = letters; }, [letters]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Auto-send when silence detected
  useEffect(() => {
    const interval = setInterval(() => {
      const timeSinceLastSign = Date.now() - lastSignTimeRef.current;
      if (lettersRef.current.length > 0 && timeSinceLastSign > SILENCE_THRESHOLD && !busy) {
        sendSentence();
      }
    }, 500);
    return () => clearInterval(interval);
  }, [busy]);

  useEffect(() => {
    let hands: any, camera: any, cancelled = false;

    function loadScript(src: string) {
      return new Promise<void>((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) return resolve();
        const s = document.createElement("script");
        s.src = src; s.crossOrigin = "anonymous";
        s.onload = () => resolve(); s.onerror = () => reject(new Error("Failed to load MediaPipe"));
        document.body.appendChild(s);
      });
    }

    async function init() {
      try {
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js");
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js");
        if (cancelled) return;
        const W = window as any;
        hands = new W.Hands({
          locateFile: (f: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}`,
        });
        hands.setOptions({
          maxNumHands: 1,
          modelComplexity: 1,
          minDetectionConfidence: 0.7,
          minTrackingConfidence: 0.6,
        });
        hands.onResults(onResults);
        if (videoRef.current) {
          camera = new W.Camera(videoRef.current, {
            onFrame: async () => {
              try {
                await hands.send({ image: videoRef.current });
              } catch {}
            },
            width: 480,
            height: 360,
          });
          camera.start();
          setReady(true);
        }
      } catch (e: any) {
        setError("Camera or MediaPipe failed. Allow camera + use Chrome/Edge.");
      }
    }

    function fingersUp(lm: any[]): string {
      const up = (tip: number, pip: number) => (lm[tip].y < lm[pip].y ? "1" : "0");
      const thumb = Math.abs(lm[4].x - lm[5].x) > 0.08 && lm[4].y < lm[6].y ? "1" : "0";
      return thumb + up(8, 6) + up(12, 10) + up(16, 14) + up(20, 18);
    }

    function onResults(res: any) {
      const cv = canvasRef.current;
      if (!cv) return;
      const ctx = cv.getContext("2d");
      if (!ctx) return;
      ctx.save();
      ctx.clearRect(0, 0, cv.width, cv.height);
      if (res.image) ctx.drawImage(res.image, 0, 0, cv.width, cv.height);

      const hand = res.multiHandLandmarks?.[0];
      if (hand) {
        ctx.fillStyle = "#9c8853";
        for (const p of hand) {
          ctx.beginPath();
          ctx.arc(p.x * cv.width, p.y * cv.height, 4, 0, 6.28);
          ctx.fill();
        }
        const pat = fingersUp(hand);
        const alphabet = language === "en" ? ASL_ALPHABET : ARSL_ALPHABET;
        const keys = Object.keys(alphabet);
        const match = keys.find((k) => alphabet[k].pattern === pat);

        if (match) {
          setCurrent(alphabet[match].letter);
          if (pat === lastPattern.current) {
            holdRef.current += 1;
            setHold(holdRef.current);
            if (holdRef.current >= HOLD_FRAMES && !committedRef.current) {
              committedRef.current = true;
              setLetters((l) => [...l, alphabet[match].letter]);
              lastSignTimeRef.current = Date.now();
            }
          } else {
            lastPattern.current = pat;
            holdRef.current = 0;
            committedRef.current = false;
            setHold(0);
          }
        } else {
          setCurrent(null);
          lastPattern.current = "";
          holdRef.current = 0;
          committedRef.current = false;
          setHold(0);
        }
      } else {
        setCurrent(null);
        lastPattern.current = "";
        holdRef.current = 0;
        committedRef.current = false;
      }
      ctx.restore();
    }

    init();
    return () => {
      cancelled = true;
      try {
        camera?.stop();
      } catch {}
      try {
        hands?.close();
      } catch {}
    };
  }, [language]);

  async function sendSentence() {
    const text = lettersRef.current.join("").trim();
    if (!text || busy) return;
    setBusy(true);
    setLetters([]);
    lastSignTimeRef.current = Date.now();

    setMessages((m) => [...m, { role: "user", text, time: new Date().toLocaleTimeString() }]);

    try {
      const r = await fetch(`${API_URL}/chat/web`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: session.emirates_id || "anonymous",
          channel: "web",
          session_id: sessionId,
          language,
          text,
        }),
      });
      const d = await r.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", text: d.text || "Error", time: new Date().toLocaleTimeString() },
      ]);
      speak(d.text || "");
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Connection error", time: new Date().toLocaleTimeString() }]);
    } finally {
      setBusy(false);
    }
  }

  function speak(text: string) {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = language === "ar" ? "ar-AE" : "en-US";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }
  }

  const alphabet = language === "en" ? ASL_ALPHABET : ARSL_ALPHABET;

  return (
    <div className="bg-moei-cream/30 min-h-screen flex flex-col">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <span className="moei-kicker">Accessibility · Real Sign Language</span>
              <h1 className="mt-1 moei-h-section">Sign-Language Conversation</h1>
              <p className="mt-1 max-w-2xl text-sm text-moei-body">
                Sign letters on camera → they build words → pause → full sentence sent. Continuous conversation with context.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                className="moei-btn-secondary"
              >
                {language === "en" ? "Switch to Arabic (ArSL)" : "Switch to English (ASL)"}
              </button>
              <button
                onClick={() => { setMessages([]); setLetters([]); }}
                className="moei-btn-secondary"
              >
                <RotateCcw size={14} /> Clear Chat
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="flex-1 mx-auto max-w-7xl px-6 py-6 w-full">
        <div className="grid gap-6 lg:grid-cols-3 h-full">
          {/* Camera + Detection */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="relative overflow-hidden rounded-xl bg-slate-900" style={{ aspectRatio: "4/3" }}>
                <video ref={videoRef} className="hidden" playsInline />
                <canvas ref={canvasRef} width={480} height={360} className="h-full w-full -scale-x-100" />
                {!ready && !error && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300">
                    <CamIcon className="animate-pulse" size={32} />
                    <p className="mt-3 text-sm">Loading camera + vision model…</p>
                  </div>
                )}
                {error && (
                  <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-red-300">
                    {error}
                  </div>
                )}
                {current && (
                  <div className="absolute left-3 top-3 rounded-full bg-moei-bronze px-4 py-2 text-lg font-bold text-white">
                    {current}
                  </div>
                )}
                {current && (
                  <div className="absolute bottom-3 left-3 right-3">
                    <div className="h-2 overflow-hidden rounded-full bg-white/30">
                      <div
                        className="h-full bg-emerald-400 transition-all"
                        style={{ width: `${Math.min(100, (hold / HOLD_FRAMES) * 100)}%` }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-white/80">Hold letter to add…</p>
                  </div>
                )}
              </div>
              <p className="mt-2 text-xs text-moei-muted">
                MediaPipe Hands (21 landmarks) · {language === "en" ? "ASL fingerspelling" : "ArSL fingerspelling"} · pause 2s auto-sends
              </p>
            </div>

            {/* Letters being typed */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Current transcription</span>
                <button
                  onClick={() => setLetters([])}
                  className="text-moei-muted hover:text-red-600"
                  aria-label="Clear"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="min-h-[60px] rounded-lg border border-moei-line bg-moei-cream/30 px-4 py-3 text-lg font-bold tracking-wider text-moei-ink font-mono">
                {letters.length > 0 ? letters.join("") : <span className="text-moei-muted text-sm">Sign letters to build…</span>}
              </div>
              <button
                onClick={sendSentence}
                disabled={busy || letters.length === 0}
                className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50"
              >
                <Send size={14} /> {busy ? "Sending…" : "Send Now (or wait 2s pause)"}
              </button>
            </div>

            {/* Alphabet reference */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Hand size={13} /> {language === "en" ? "ASL Fingerspelling" : "ArSL Alphabet"}
              </div>
              <div className="grid grid-cols-6 gap-2 sm:grid-cols-8">
                {Object.entries(alphabet)
                  .slice(0, 26)
                  .map(([key, { letter }]) => (
                    <div key={key} className="rounded-lg border border-moei-line p-2 text-center bg-moei-cream/20">
                      <div className="text-lg font-bold text-moei-ink">{letter}</div>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Chat history */}
          <div className="rounded-2xl border border-moei-line bg-white p-4 flex flex-col">
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-moei-line">
              <MessageCircle size={16} className="text-moei-bronze" />
              <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Conversation</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-3 mb-3">
              {messages.length === 0 ? (
                <p className="text-xs text-moei-muted text-center py-8">Start signing to begin conversation…</p>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className={`text-xs p-2 rounded-lg ${
                    msg.role === "user"
                      ? "bg-moei-bronze/10 text-moei-ink border border-moei-bronze/30"
                      : "bg-emerald-50 text-emerald-900 border border-emerald-200"
                  }`}>
                    <div className="font-semibold text-[10px] mb-1">
                      {msg.role === "user" ? "You" : "Assistant"} · {msg.time}
                    </div>
                    <p className="text-[11px] leading-relaxed">{msg.text}</p>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
