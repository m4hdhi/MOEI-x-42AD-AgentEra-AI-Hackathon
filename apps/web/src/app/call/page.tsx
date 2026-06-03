"use client";

/**
 * Live voice agent call (citizen surface).
 *
 *   citizen speaks → browser STT (Web Speech API) → /chat /web supervisor (channel=voice)
 *                  → reply text → /voice/tts (ElevenLabs)  → audio plays
 *                                                fallback → window.speechSynthesis
 *
 * No real phone number / no Twilio Voice / no SIP. Just a browser tab that LOOKS like
 * a phone call so the demo flows cleanly.
 */

import { useEffect, useRef, useState } from "react";
import { Phone, PhoneOff, Mic, Volume2, AlertCircle } from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

type Turn = { role: "agent" | "citizen"; text: string; t?: number };
type CallState = "idle" | "ringing" | "connected" | "listening" | "thinking" | "speaking" | "saving";

type SpeechRec = any;

export default function CallPage() {
  return (
    <LoginGate
      theme="dark"
      title="Sign in to call the MOEI Smart Assistant"
      subtitle="We connect you to the right service and keep a record of your call against your file, so any officer can follow up."
    >
      {(session) => <CallExperience session={session} />}
    </LoginGate>
  );
}

function CallExperience({ session }: { session: UaePassSession }) {
  const callerId = session.emirates_id || "anonymous";
  const callerName = session.full_name_en || "";
  const [state, setState] = useState<CallState>("idle");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [duration, setDuration] = useState(0);
  const [usingEleven, setUsingEleven] = useState<boolean | null>(null);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [tone, setTone] = useState<number | null>(null); // live sentiment 0..1
  const [caseNumber, setCaseNumber] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [sessionId] = useState(() => crypto.randomUUID());

  const recogRef = useRef<SpeechRec | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const stateRef = useRef<CallState>("idle");
  useEffect(() => { stateRef.current = state; }, [state]);

  // Recording: mic stream + MediaRecorder + chunk buffer.
  const mediaRecRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  // Keep the latest transcript + call start in refs so the hang-up handler isn't stale.
  const transcriptRef = useRef<Turn[]>([]);
  const callStartRef = useRef<number>(0);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  const elapsed = () => (callStartRef.current ? Math.floor((Date.now() - callStartRef.current) / 1000) : 0);

  // Probe ElevenLabs availability once
  useEffect(() => {
    fetch(`${API_URL}/voice/tts/status`)
      .then(r => r.json())
      .then(d => setUsingEleven(!!d.available))
      .catch(() => setUsingEleven(false));
  }, []);

  // Init browser STT once
  useEffect(() => {
    if (typeof window === "undefined") return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setError("Voice not supported in this browser. Try Chrome or Edge.");
      return;
    }
    const r = new SR();
    r.continuous = false;
    r.interimResults = true;
    r.lang = "en-US";
    r.onresult = (e: any) => {
      let final = "";
      let inter = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t;
        else inter += t;
      }
      setInterim(inter);
      if (final.trim()) {
        handleCitizenSpeech(final.trim());
        setInterim("");
      }
    };
    r.onerror = (e: any) => {
      console.warn("STT error", e.error);
      if (stateRef.current === "listening") setState("connected");
    };
    r.onend = () => {
      if (stateRef.current === "listening") {
        // Restart STT loop if we're still expecting the citizen to talk
        try { r.start(); } catch {}
      }
    };
    recogRef.current = r;
    return () => { try { r.stop(); } catch {} };
  }, []);

  async function startCall() {
    if (state !== "idle") return;
    setError(null);
    setTranscript([]);
    setDuration(0);
    setSaved(false);
    setTone(null);
    setCaseNumber(null);
    setSources([]);
    setState("ringing");

    // Request the mic and start recording the call audio.
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm"
                 : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "";
      const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunksRef.current.push(e.data); };
      rec.start(1000); // gather a chunk every second
      mediaRecRef.current = rec;
    } catch (e) {
      // Mic denied — call still works (we have the transcript), just no audio file.
      console.warn("mic capture unavailable", e);
    }

    callStartRef.current = Date.now();
    setTimeout(() => {
      setState("connected");
      const opener = "Hello, you've reached the Ministry of Energy and Infrastructure. How can I help you today?";
      speak(opener, "en");
      setTranscript([{ role: "agent", text: opener, t: 0 }]);
      timerRef.current = window.setInterval(() => setDuration(d => d + 1), 1000) as unknown as number;
    }, 1200);
  }

  function endCall() {
    setInterim("");
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    try { recogRef.current?.stop(); } catch {}
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();

    const turns = transcriptRef.current;
    const callDuration = elapsed();
    const hadConversation = turns.filter((t) => t.role === "citizen").length > 0;

    // Stop the recorder, then upload audio + transcript once the final chunk lands.
    const rec = mediaRecRef.current;
    const finishUpload = (blob: Blob | null) => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      mediaRecRef.current = null;
      if (hadConversation) {
        uploadRecording(blob, turns, callDuration);
      } else {
        setState("idle");
      }
    };

    if (rec && rec.state !== "inactive") {
      setState("saving");
      rec.onstop = () => {
        const type = rec.mimeType || "audio/webm";
        const blob = chunksRef.current.length ? new Blob(chunksRef.current, { type }) : null;
        finishUpload(blob);
      };
      try { rec.stop(); } catch { finishUpload(null); }
    } else {
      if (hadConversation) { setState("saving"); }
      finishUpload(null);
    }
  }

  async function uploadRecording(blob: Blob | null, turns: Turn[], callDuration: number) {
    try {
      const fd = new FormData();
      fd.append("call_id", sessionId);
      fd.append("language", "en");
      fd.append("user_id", callerId);
      fd.append("user_name", callerName);
      fd.append("duration_seconds", String(callDuration));
      fd.append("transcript", JSON.stringify(turns));
      if (blob && blob.size > 0) {
        const ext = (blob.type.includes("mp4")) ? "mp4" : "webm";
        fd.append("audio", blob, `call.${ext}`);
      }
      await fetch(`${API_URL}/recordings`, { method: "POST", body: fd, credentials: "include" });
      setSaved(true);
    } catch (e) {
      console.warn("recording upload failed", e);
    } finally {
      setState("idle");
    }
  }

  function startListening() {
    const r = recogRef.current;
    if (!r) return;
    setState("listening");
    try { r.lang = "en-US"; r.start(); } catch {}
  }

  async function handleCitizenSpeech(text: string) {
    setTranscript((t) => [...t, { role: "citizen", text, t: elapsed() }]);
    setState("thinking");
    try { recogRef.current?.stop(); } catch {}

    try {
      const res = await fetch(`${API_URL}/voice/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: callerId,
          channel: "voice",
          session_id: sessionId,
          language: "auto",
          text,
        }),
      });
      const data = await res.json();
      const reply: string = data.text || "I didn't catch that, could you say it again?";
      const lang: string = data.language || "en";
      if (typeof data.sentiment === "number") setTone(data.sentiment);
      if (data.case_number) setCaseNumber(data.case_number);
      if (Array.isArray(data.citations) && data.citations.length) {
        setSources(data.citations.map((c: any) => c.title).filter(Boolean));
      }
      setTranscript((t) => [...t, { role: "agent", text: reply, t: elapsed() }]);
      await speak(reply, lang);
    } catch (e: any) {
      setError("Connection lost. Please try again.");
      setState("connected");
    }
  }

  async function speak(text: string, language: string) {
    setState("speaking");
    try {
      // Try ElevenLabs first if we know it's available
      if (usingEleven !== false) {
        const r = await fetch(`${API_URL}/voice/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language }),
        });
        if (r.ok && r.headers.get("content-type")?.includes("audio")) {
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const a = new Audio(url);
          audioRef.current = a;
          await new Promise<void>((resolve) => {
            a.onended = () => resolve();
            a.onerror = () => resolve();
            a.play().catch(() => resolve());
          });
          URL.revokeObjectURL(url);
          if (stateRef.current !== "idle") setState("connected");
          // After Hassan finishes, immediately listen for the citizen
          setTimeout(() => { if (stateRef.current === "connected") startListening(); }, 150);
          return;
        }
        // 503 → fall through to browser TTS
        setUsingEleven(false);
      }
      // Browser TTS fallback (free, no API)
      await new Promise<void>((resolve) => {
        if (typeof window === "undefined" || !window.speechSynthesis) { resolve(); return; }
        const u = new SpeechSynthesisUtterance(text);
        u.lang = language === "ar" ? "ar-AE" : "en-US";
        u.rate = 1.05;
        u.onend = () => resolve();
        u.onerror = () => resolve();
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      });
      if (stateRef.current !== "idle") setState("connected");
      setTimeout(() => { if (stateRef.current === "connected") startListening(); }, 150);
    } catch {
      if (stateRef.current !== "idle") setState("connected");
    }
  }

  const fmtDuration = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const r = (s % 60).toString().padStart(2, "0");
    return `${m}:${r}`;
  };

  return (
    <div className="min-h-[calc(100vh-200px)] bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 py-16">
      <div className="mx-auto max-w-md px-6">
        <div className="rounded-3xl border border-slate-700/50 bg-slate-800/80 p-8 shadow-2xl backdrop-blur">
          {/* Header */}
          <div className="text-center">
            <div className="inline-flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-moei-bronze to-moei-bronze-dark shadow-lg">
              <Phone className="text-white" size={28} />
            </div>
            <h2 className="mt-4 text-xl font-bold text-white">MOEI Call Centre</h2>
            <p className="text-[11px] uppercase tracking-wider text-slate-400">Customer Happiness Centre · 800 6634</p>

            {/* Status */}
            <div className="mt-4 flex items-center justify-center gap-2 text-xs">
              {state === "idle" && (
                <span className="rounded-full bg-slate-700 px-3 py-1 text-slate-300">Not connected</span>
              )}
              {state === "ringing" && (
                <span className="animate-pulse rounded-full bg-amber-500/20 px-3 py-1 text-amber-300">Connecting…</span>
              )}
              {state === "connected" && (
                <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-emerald-300">● Connected · {fmtDuration(duration)}</span>
              )}
              {state === "listening" && (
                <span className="animate-pulse rounded-full bg-red-500/20 px-3 py-1 text-red-300">● Listening · {fmtDuration(duration)}</span>
              )}
              {state === "thinking" && (
                <span className="rounded-full bg-blue-500/20 px-3 py-1 text-blue-300">… One moment</span>
              )}
              {state === "speaking" && (
                <span className="animate-pulse rounded-full bg-moei-bronze/20 px-3 py-1 text-moei-bronze">🔊 Speaking</span>
              )}
              {state === "saving" && (
                <span className="animate-pulse rounded-full bg-blue-500/20 px-3 py-1 text-blue-300">Saving call record…</span>
              )}
            </div>

            {/* Recording indicator — realistic contact-centre cue */}
            {state !== "idle" && state !== "saving" && (
              <div className="mt-2 flex items-center justify-center gap-1.5 text-[10px] text-slate-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                Recording · this call is logged for quality and follow-up
              </div>
            )}

            {/* Live voice tone (real-time sentiment) */}
            {state !== "idle" && state !== "saving" && tone !== null && (() => {
              const t = tone;
              const meta = t < 0.35
                ? { label: "Frustrated", emoji: "😠", cls: "bg-red-500/20 text-red-300" }
                : t < 0.5
                ? { label: "Stressed", emoji: "😟", cls: "bg-amber-500/20 text-amber-300" }
                : t < 0.7
                ? { label: "Neutral", emoji: "😐", cls: "bg-slate-600/40 text-slate-300" }
                : { label: "Satisfied", emoji: "🙂", cls: "bg-emerald-500/20 text-emerald-300" };
              return (
                <div className="mt-3 flex items-center justify-center gap-2">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500">Live tone</span>
                  <span className={"inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold " + meta.cls}>
                    {meta.emoji} {meta.label}
                  </span>
                  <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700">
                    <div
                      className={"h-full transition-all " + (t < 0.35 ? "bg-red-400" : t < 0.5 ? "bg-amber-400" : t < 0.7 ? "bg-slate-400" : "bg-emerald-400")}
                      style={{ width: `${Math.round(t * 100)}%` }}
                    />
                  </div>
                </div>
              );
            })()}
            {saved && state === "idle" && (
              <div className="mt-2 text-[10px] text-emerald-400">
                ✓ Call saved. A summary and any follow-up have been logged to your case file.
              </div>
            )}
          </div>

          {/* Waveform / pulse */}
          <div className="mt-6 flex h-20 items-center justify-center gap-1">
            {Array.from({ length: 24 }).map((_, i) => {
              const active = state === "listening" || state === "speaking";
              const h = active ? 6 + ((Math.sin(i * 0.6 + duration * 2) + 1) * 16) : 4;
              return (
                <div
                  key={i}
                  className={
                    "w-1 rounded-full transition-all " +
                    (state === "listening" ? "bg-red-400" : state === "speaking" ? "bg-moei-bronze" : "bg-slate-700")
                  }
                  style={{ height: `${h}px` }}
                />
              );
            })}
          </div>

          {/* Interim transcript */}
          {interim && (
            <div className="mt-2 text-center text-xs italic text-slate-400">“{interim}…”</div>
          )}

          {/* Transcript */}
          <div className="mt-6 max-h-56 overflow-y-auto rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            {transcript.length === 0 ? (
              <p className="text-center text-[11px] text-slate-500">
                Tap the green button to start the call.
              </p>
            ) : (
              <ul className="space-y-2 text-[12px]">
                {transcript.map((t, i) => (
                  <li key={i} className="flex gap-2">
                    <span className={"shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase " + (t.role === "agent" ? "bg-moei-bronze text-white" : "bg-slate-700 text-slate-200")}>
                      {t.role === "agent" ? "MOEI" : "You"}
                    </span>
                    <span className="text-slate-200">{t.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Grounding proof: live case + official sources used */}
          {(caseNumber || sources.length > 0) && state !== "idle" && (
            <div className="mt-3 space-y-1.5">
              {caseNumber && (
                <div className="flex items-center justify-center gap-1.5 text-[11px] text-emerald-300">
                  ✓ Logged as case <span className="font-mono font-semibold">{caseNumber}</span>
                </div>
              )}
              {sources.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-1 text-[10px] text-slate-400">
                  <span className="uppercase tracking-wider text-slate-500">Sources:</span>
                  {sources.slice(0, 3).map((s) => (
                    <span key={s} className="rounded-full bg-slate-700/60 px-2 py-0.5 text-slate-300">{s}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Controls */}
          <div className="mt-6 flex items-center justify-center gap-4">
            {state === "idle" ? (
              <button
                onClick={startCall}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 text-white shadow-lg transition hover:bg-emerald-600"
                aria-label="Start call"
              >
                <Phone size={26} />
              </button>
            ) : (
              <button
                onClick={endCall}
                disabled={state === "saving"}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:bg-red-600 disabled:opacity-50"
                aria-label="End call"
              >
                <PhoneOff size={26} />
              </button>
            )}
            {state === "connected" && (
              <button
                onClick={startListening}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-700 text-white transition hover:bg-slate-600"
                aria-label="Speak now"
                title="Speak"
              >
                <Mic size={18} />
              </button>
            )}
          </div>

          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          <div className="mt-5 flex items-center justify-center gap-2 text-[10px] text-slate-500">
            <Volume2 size={12} />
            High-quality voice
          </div>
        </div>
        <p className="mt-4 text-center text-[10px] text-slate-500">
          Customer Happiness Centre · Arabic and English supported · Available 24/7
        </p>
      </div>
    </div>
  );
}
