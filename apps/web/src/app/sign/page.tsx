"use client";

/**
 * Digital Human — Sign-Language input (accessibility / inclusion).
 *
 * Real computer vision in the browser: Google MediaPipe Hands tracks 21 hand landmarks per
 * frame; we classify the finger pattern into a vocabulary of common service signs (shown in
 * English + Arabic), build a sentence, and send it to the MOEI Smart Assistant — so a Deaf
 * citizen can be served without typing or speaking. Runs fully client-side, no GPU server.
 */

import { useEffect, useRef, useState } from "react";
import { Hand, Send, Trash2, Volume2, Camera as CamIcon } from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// Vocabulary: [thumb, index, middle, ring, pinky] up-pattern → word (EN/AR).
const SIGNS: { pattern: string; en: string; ar: string; emoji: string }[] = [
  { pattern: "01111", en: "Hello", ar: "مرحبا", emoji: "🖐️" },
  { pattern: "00000", en: "Yes", ar: "نعم", emoji: "✊" },
  { pattern: "00001", en: "No", ar: "لا", emoji: "🤙" },
  { pattern: "10000", en: "Thank you", ar: "شكرا", emoji: "👍" },
  { pattern: "01000", en: "Help", ar: "مساعدة", emoji: "☝️" },
  { pattern: "01100", en: "Status", ar: "الحالة", emoji: "✌️" },
  { pattern: "01110", en: "Housing", ar: "السكن", emoji: "🤟" },
  { pattern: "11111", en: "Energy", ar: "الطاقة", emoji: "🖐️" },
];
const SIGN_MAP = Object.fromEntries(SIGNS.map((s) => [s.pattern, s]));
const HOLD_FRAMES = 12; // ~0.8s of a stable sign to commit a word

export default function SignPage() {
  return (
    <LoginGate
      title="Sign in to use Sign-Language assistant"
      subtitle="An inclusive way to reach MOEI: sign to your camera and we'll understand. Sign in with UAE PASS to begin."
    >
      {(session) => <SignExperience session={session} />}
    </LoginGate>
  );
}

function SignExperience({ session }: { session: UaePassSession }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<{ en: string; ar: string; emoji: string } | null>(null);
  const [hold, setHold] = useState(0);
  const [words, setWords] = useState<string[]>([]);
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // refs that the detection loop reads without re-subscribing
  const lastSign = useRef<string>("");
  const holdRef = useRef(0);
  const committedRef = useRef(false);
  const wordsRef = useRef<string[]>([]);
  useEffect(() => { wordsRef.current = words; }, [words]);

  useEffect(() => {
    let hands: any, camera: any, cancelled = false;

    function loadScript(src: string) {
      return new Promise<void>((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) return resolve();
        const s = document.createElement("script");
        s.src = src; s.crossOrigin = "anonymous";
        s.onload = () => resolve(); s.onerror = () => reject(new Error("load failed: " + src));
        document.body.appendChild(s);
      });
    }

    async function init() {
      try {
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js");
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js");
        if (cancelled) return;
        const W = window as any;
        hands = new W.Hands({ locateFile: (f: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}` });
        hands.setOptions({ maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: 0.7, minTrackingConfidence: 0.6 });
        hands.onResults(onResults);
        if (videoRef.current) {
          camera = new W.Camera(videoRef.current, {
            onFrame: async () => { try { await hands.send({ image: videoRef.current }); } catch {} },
            width: 480, height: 360,
          });
          camera.start();
          setReady(true);
        }
      } catch (e: any) {
        setError("Could not start the camera or load the vision model. Allow camera access and use Chrome/Edge.");
      }
    }

    function fingersUp(lm: any[]): string {
      // y grows downward. A finger is up if its tip is above its PIP joint.
      const up = (tip: number, pip: number) => (lm[tip].y < lm[pip].y ? "1" : "0");
      // Thumb: extended sideways — tip far in x from the index MCP.
      const thumb = Math.abs(lm[4].x - lm[5].x) > 0.08 && lm[4].y < lm[6].y ? "1" : "0";
      return thumb + up(8, 6) + up(12, 10) + up(16, 14) + up(20, 18);
    }

    function onResults(res: any) {
      const cv = canvasRef.current; if (!cv) return;
      const ctx = cv.getContext("2d"); if (!ctx) return;
      ctx.save(); ctx.clearRect(0, 0, cv.width, cv.height);
      if (res.image) ctx.drawImage(res.image, 0, 0, cv.width, cv.height);

      const hand = res.multiHandLandmarks?.[0];
      if (hand) {
        // draw landmarks
        ctx.fillStyle = "#9c8853";
        for (const p of hand) { ctx.beginPath(); ctx.arc(p.x * cv.width, p.y * cv.height, 4, 0, 6.28); ctx.fill(); }
        const pat = fingersUp(hand);
        const sign = SIGN_MAP[pat];
        if (sign) {
          setCurrent({ en: sign.en, ar: sign.ar, emoji: sign.emoji });
          if (pat === lastSign.current) {
            holdRef.current += 1;
            setHold(holdRef.current);
            if (holdRef.current >= HOLD_FRAMES && !committedRef.current) {
              committedRef.current = true;
              setWords((w) => [...w, sign.en]);
            }
          } else {
            lastSign.current = pat; holdRef.current = 0; committedRef.current = false; setHold(0);
          }
        } else {
          setCurrent(null); lastSign.current = ""; holdRef.current = 0; committedRef.current = false; setHold(0);
        }
      } else {
        setCurrent(null); lastSign.current = ""; holdRef.current = 0; committedRef.current = false;
      }
      ctx.restore();
    }

    init();
    return () => { cancelled = true; try { camera?.stop(); } catch {} try { hands?.close(); } catch {} };
  }, []);

  async function sendToAssistant() {
    const text = wordsRef.current.join(" ").trim();
    if (!text || busy) return;
    setBusy(true); setReply(null);
    try {
      const r = await fetch(`${API_URL}/chat/web`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({
          user_id: session.emirates_id || "anonymous", channel: "web",
          session_id: "sign-" + Date.now(), language: "auto", text,
        }),
      });
      const d = await r.json();
      setReply(d.text || "");
    } catch { setReply("Connection error. Please try again."); }
    finally { setBusy(false); }
  }

  function speak() {
    if (reply && typeof window !== "undefined" && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(reply); u.lang = /[؀-ۿ]/.test(reply) ? "ar-AE" : "en-US";
      window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
    }
  }

  return (
    <div className="bg-moei-cream/30 min-h-screen">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-5xl px-6 py-8">
          <span className="moei-kicker">Accessibility · Digital Human</span>
          <h1 className="mt-2 moei-h-section">Sign-Language Assistant</h1>
          <p className="mt-2 max-w-2xl text-sm text-moei-body">
            Sign to your camera — we recognise the gesture and build your request, then the
            assistant replies. Real-time hand tracking runs privately in your browser.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Camera */}
          <div className="rounded-2xl border border-moei-line bg-white p-4">
            <div className="relative overflow-hidden rounded-xl bg-slate-900" style={{ aspectRatio: "4/3" }}>
              <video ref={videoRef} className="hidden" playsInline />
              <canvas ref={canvasRef} width={480} height={360} className="h-full w-full -scale-x-100" />
              {!ready && !error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300">
                  <CamIcon className="animate-pulse" size={28} />
                  <p className="mt-2 text-xs">Starting camera + vision model…</p>
                </div>
              )}
              {error && (
                <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300">{error}</div>
              )}
              {/* Live detection badge */}
              {current && (
                <div className="absolute left-3 top-3 rounded-full bg-moei-bronze px-3 py-1 text-sm font-bold text-white">
                  {current.emoji} {current.en} · {current.ar}
                </div>
              )}
              {current && (
                <div className="absolute bottom-3 left-3 right-3">
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/30">
                    <div className="h-full bg-emerald-400 transition-all" style={{ width: `${Math.min(100, (hold / HOLD_FRAMES) * 100)}%` }} />
                  </div>
                  <div className="mt-1 text-[10px] text-white/80">Hold the sign to add the word…</div>
                </div>
              )}
            </div>
            <p className="mt-2 text-[10px] text-moei-muted">
              Computer vision: MediaPipe Hands (21 landmarks) · runs locally, no video leaves your device.
            </p>
          </div>

          {/* Builder + reply */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Your message</span>
                <button onClick={() => setWords([])} className="text-moei-muted hover:text-red-600" aria-label="Clear"><Trash2 size={14} /></button>
              </div>
              <div className="mt-2 min-h-[48px] rounded-lg border border-moei-line bg-moei-cream/30 px-3 py-2 text-sm text-moei-ink">
                {words.length ? words.join(" ") : <span className="text-moei-muted">Sign to build your message…</span>}
              </div>
              <button
                onClick={sendToAssistant}
                disabled={busy || words.length === 0}
                className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50"
              >
                <Send size={14} /> {busy ? "Sending…" : "Send to assistant"}
              </button>
            </div>

            {reply && (
              <div className="rounded-2xl border border-moei-bronze/40 bg-moei-cream/40 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-moei-bronze">Assistant reply</span>
                  <button onClick={speak} className="text-moei-bronze hover:text-moei-bronze-dark" aria-label="Read aloud"><Volume2 size={15} /></button>
                </div>
                <p className="mt-2 whitespace-pre-line text-sm text-moei-ink">{reply}</p>
              </div>
            )}

            {/* Legend */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Hand size={13} /> Recognised signs
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {SIGNS.map((s) => (
                  <div key={s.pattern} className="rounded-lg border border-moei-line p-2 text-center">
                    <div className="text-xl">{s.emoji}</div>
                    <div className="text-[11px] font-semibold text-moei-ink">{s.en}</div>
                    <div className="text-[10px] text-moei-muted">{s.ar}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
