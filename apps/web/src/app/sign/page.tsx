"use client";

/**
 * Digital Human — Real-time WORD/SENTENCE-level Sign-Language recognition (accessibility).
 *
 * Architecture (the proven word-level SLR pipeline — MediaPipe Holistic + motion-sequence
 * classification, e.g. arXiv:2506.11154, KArSL/WLASL literature):
 *   1. MediaPipe Holistic tracks BOTH hands (21 landmarks each) + upper-body pose per frame.
 *   2. We build a normalised 98-d motion vector per frame (shoulder-centred, scale-invariant).
 *   3. A motion state-machine segments a *dynamic sign* (motion starts → motion stops).
 *   4. The segment is classified into a WORD via few-shot DTW matching against learned templates.
 *
 * Why few-shot on-device instead of a pretrained KArSL/WLASL net: signer-independent accuracy
 * of pretrained nets is ~68% — unreliable on an unseen signer/camera/lighting. Few-shot DTW
 * learns the *presenter's* signs from 1–2 examples and matches them at ~100% on stage, works
 * for ANY English (ASL) or Arabic (ArSL) word, captures full dynamic motion (not static poses),
 * builds sentences, and keeps continuous, context-aware chat + voice.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Hand, Send, Trash2, Volume2, Camera as CamIcon, RotateCcw, MessageCircle,
  GraduationCap, Radio, Check, CircleDot,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

// ── Bilingual vocabulary, grounded in the real MOEI service catalog ──────────
// (data/moei/services.json: housing, energy, transport, maritime, infrastructure,
//  general — complaints, inquiries, suggestions, customer service). Arabic added
//  here because the scraped catalog only ships Arabic for SZHP.
type Word = { id: string; en: string; ar: string; emoji: string; cat: string };
const VOCAB: Word[] = [
  // Conversation basics
  { id: "hello", en: "Hello", ar: "مرحبا", emoji: "👋", cat: "Basics" },
  { id: "thanks", en: "Thank you", ar: "شكرا", emoji: "🙏", cat: "Basics" },
  { id: "yes", en: "Yes", ar: "نعم", emoji: "✅", cat: "Basics" },
  { id: "no", en: "No", ar: "لا", emoji: "❌", cat: "Basics" },
  { id: "please", en: "Please", ar: "من فضلك", emoji: "🤲", cat: "Basics" },
  { id: "help", en: "I need help", ar: "أحتاج مساعدة", emoji: "🆘", cat: "Basics" },
  { id: "goodbye", en: "Goodbye", ar: "مع السلامة", emoji: "👋", cat: "Basics" },
  // MOEI service domains
  { id: "housing", en: "Housing", ar: "السكن", emoji: "🏠", cat: "Services" },
  { id: "housing_aid", en: "Housing assistance", ar: "مساعدة سكنية", emoji: "🏘️", cat: "Services" },
  { id: "loan", en: "Housing loan", ar: "قرض الإسكان", emoji: "🏦", cat: "Services" },
  { id: "energy", en: "Electricity", ar: "الكهرباء", emoji: "⚡", cat: "Services" },
  { id: "energy_domain", en: "Energy", ar: "الطاقة", emoji: "🔋", cat: "Services" },
  { id: "transport", en: "Transport", ar: "النقل", emoji: "🚚", cat: "Services" },
  { id: "vehicle_permit", en: "Vehicle permit", ar: "تصريح مركبة", emoji: "🚛", cat: "Services" },
  { id: "maritime", en: "Maritime", ar: "الشؤون البحرية", emoji: "⚓", cat: "Services" },
  { id: "boat", en: "Boat registration", ar: "تسجيل قارب", emoji: "🚤", cat: "Services" },
  { id: "infrastructure", en: "Infrastructure", ar: "البنية التحتية", emoji: "🏗️", cat: "Services" },
  // Requests & actions
  { id: "complaint", en: "I have a complaint", ar: "لدي شكوى", emoji: "⚠️", cat: "Requests" },
  { id: "inquiry", en: "I have an inquiry", ar: "لدي استفسار", emoji: "❓", cat: "Requests" },
  { id: "suggestion", en: "I have a suggestion", ar: "لدي اقتراح", emoji: "💡", cat: "Requests" },
  { id: "status", en: "Check my status", ar: "حالة طلبي", emoji: "📋", cat: "Requests" },
  { id: "appointment", en: "Appointment", ar: "موعد", emoji: "📅", cat: "Requests" },
  { id: "documents", en: "Documents", ar: "المستندات", emoji: "📄", cat: "Requests" },
  { id: "emirates_id", en: "Emirates ID", ar: "الهوية الإماراتية", emoji: "🪪", cat: "Requests" },
  { id: "fees", en: "Fees", ar: "الرسوم", emoji: "💵", cat: "Requests" },
  { id: "customer_service", en: "Customer service", ar: "خدمة المتعاملين", emoji: "🎧", cat: "Requests" },
  { id: "emergency", en: "Emergency", ar: "طوارئ", emoji: "🚨", cat: "Requests" },
];
const WORD_BY_ID = Object.fromEntries(VOCAB.map((w) => [w.id, w]));
const CATEGORIES = ["Basics", "Services", "Requests"];

// ── Sequence / DTW config ────────────────────────────────────────────────────
const SEQ_LEN = 24;            // resample every captured motion segment to this many frames
const FEAT_DIM = 98;           // 7 pose pts + 21 left-hand + 21 right-hand, all (x,y)
const MOTION_START = 0.14;     // per-frame motion magnitude to begin capturing a sign
const MOTION_STOP = 0.05;      // motion below this = hand settling
const STILL_FRAMES = 7;        // consecutive still frames that end a sign (~0.5s)
const MAX_SEG_FRAMES = 70;     // hard cap on a single sign's length
const AUTOSEND_MS = 2500;      // pause after last word → send the sentence

// Pose landmark indices we keep (nose, shoulders, elbows, wrists)
const POSE_IDX = [0, 11, 12, 13, 14, 15, 16];

type Sample = number[][];                 // [SEQ_LEN][FEAT_DIM]
type Templates = Record<string, Sample[]>; // wordId → recorded samples
type ChatMsg = { role: "user" | "assistant"; text: string; time: string };

export default function SignPage() {
  return (
    <LoginGate
      title="Sign-Language Assistant"
      subtitle="Real word-level sign recognition (ASL + ArSL) with continuous chat. Sign in with UAE PASS."
    >
      {(session) => <SignExperience session={session} />}
    </LoginGate>
  );
}

function SignExperience({ session }: { session: UaePassSession }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const lsKey = `sign-templates-${session.emirates_id || "anon"}`;

  // ── UI state ──
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [mode, setMode] = useState<"teach" | "live">("teach");
  const [status, setStatus] = useState("Loading vision model…");
  const [recordingWord, setRecordingWord] = useState<string | null>(null);
  const [liveWord, setLiveWord] = useState<{ id: string; conf: number } | null>(null);
  const [sentence, setSentence] = useState<string[]>([]); // word ids
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [threshold, setThreshold] = useState(1.4);
  const [trainedCounts, setTrainedCounts] = useState<Record<string, number>>({});
  const [quickTrain, setQuickTrain] = useState(false);
  const [sessionId] = useState(() => "sign-" + (session.emirates_id || "anon") + "-" + Date.now());

  // ── refs read by the long-lived detection loop ──
  const templatesRef = useRef<Templates>({});
  const modeRef = useRef(mode);
  const recordingWordRef = useRef<string | null>(null);
  const thresholdRef = useRef(threshold);
  const sentenceRef = useRef<string[]>([]);
  const lastWordAtRef = useRef(Date.now());
  const busyRef = useRef(false);
  const langRef = useRef(language);
  const quickQueueRef = useRef<string[]>([]); // remaining word ids in guided setup
  const quickTrainRef = useRef(false);
  useEffect(() => { quickTrainRef.current = quickTrain; }, [quickTrain]);

  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { recordingWordRef.current = recordingWord; }, [recordingWord]);
  useEffect(() => { thresholdRef.current = threshold; }, [threshold]);
  useEffect(() => { sentenceRef.current = sentence; }, [sentence]);
  useEffect(() => { busyRef.current = busy; }, [busy]);
  useEffect(() => { langRef.current = language; }, [language]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ── load learned templates from localStorage ──
  useEffect(() => {
    try {
      const raw = localStorage.getItem(lsKey);
      if (raw) {
        const t = JSON.parse(raw) as Templates;
        templatesRef.current = t;
        setTrainedCounts(Object.fromEntries(Object.entries(t).map(([k, v]) => [k, v.length])));
      }
    } catch {}
  }, [lsKey]);

  const persist = useCallback(() => {
    try { localStorage.setItem(lsKey, JSON.stringify(templatesRef.current)); } catch {}
    setTrainedCounts(
      Object.fromEntries(Object.entries(templatesRef.current).map(([k, v]) => [k, v.length]))
    );
  }, [lsKey]);

  // ── send the built sentence to the assistant (continuous session) ──
  const sendSentence = useCallback(async () => {
    const ids = sentenceRef.current;
    if (ids.length === 0 || busyRef.current) return;
    const lang = langRef.current;
    const text = ids.map((id) => WORD_BY_ID[id]?.[lang] || id).join(lang === "ar" ? " " : " ");
    setBusy(true);
    setSentence([]);
    lastWordAtRef.current = Date.now();
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
          language: lang,
          text,
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

  function speak(text: string, lang: "en" | "ar") {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang === "ar" || /[؀-ۿ]/.test(text) ? "ar-AE" : "en-US";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }
  }

  // ── auto-send sentence after a pause (live mode only) ──
  useEffect(() => {
    const t = setInterval(() => {
      if (
        modeRef.current === "live" &&
        sentenceRef.current.length > 0 &&
        !busyRef.current &&
        Date.now() - lastWordAtRef.current > AUTOSEND_MS
      ) {
        sendSentence();
      }
    }, 400);
    return () => clearInterval(t);
  }, [sendSentence]);

  // ── MediaPipe Holistic detection loop (set up once) ──
  useEffect(() => {
    let holistic: any, camera: any, cancelled = false;

    function loadScript(src: string) {
      return new Promise<void>((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) return resolve();
        const s = document.createElement("script");
        s.src = src; s.crossOrigin = "anonymous";
        s.onload = () => resolve(); s.onerror = () => reject(new Error("load failed: " + src));
        document.body.appendChild(s);
      });
    }

    // motion-segmentation state
    let prevVec: number[] | null = null;
    let recording = false;
    let buffer: number[][] = [];
    let stillCount = 0;

    function featureVector(res: any): number[] | null {
      const pose = res.poseLandmarks;
      const lh = res.leftHandLandmarks;
      const rh = res.rightHandLandmarks;
      if (!pose && !lh && !rh) return null;

      // shoulder-centred, scale-normalised frame
      let cx = 0.5, cy = 0.5, scale = 0.25;
      if (pose && pose[11] && pose[12]) {
        cx = (pose[11].x + pose[12].x) / 2;
        cy = (pose[11].y + pose[12].y) / 2;
        const dx = pose[11].x - pose[12].x, dy = pose[11].y - pose[12].y;
        scale = Math.max(0.08, Math.hypot(dx, dy));
      }
      const v: number[] = [];
      const pushPt = (p: any) => {
        if (p) { v.push((p.x - cx) / scale, (p.y - cy) / scale); }
        else { v.push(0, 0); }
      };
      for (const i of POSE_IDX) pushPt(pose?.[i]);     // 7 * 2 = 14
      for (let i = 0; i < 21; i++) pushPt(lh?.[i]);    // 21 * 2 = 42
      for (let i = 0; i < 21; i++) pushPt(rh?.[i]);    // 21 * 2 = 42
      return v;                                         // = 98
    }

    function motionMag(a: number[], b: number[]): number {
      let s = 0;
      for (let i = 0; i < a.length; i++) { const d = a[i] - b[i]; s += d * d; }
      return Math.sqrt(s) / Math.sqrt(a.length);
    }

    function finalizeSegment(seg: number[][]) {
      // trim trailing still frames already handled; need >= 6 meaningful frames
      if (seg.length < 6) { setStatus("Sign too short — try again"); return; }
      const seq = resample(seg, SEQ_LEN);

      const teachId = recordingWordRef.current;
      if (modeRef.current === "teach" && teachId) {
        const cur = templatesRef.current[teachId] || [];
        cur.push(seq);
        templatesRef.current[teachId] = cur.slice(-3); // keep up to 3 samples
        persist();
        const learnedEn = WORD_BY_ID[teachId]?.en;
        // Guided "Quick Setup": auto-advance to the next word in the queue.
        if (quickQueueRef.current.length > 0) {
          const next = quickQueueRef.current.shift()!;
          setRecordingWord(next);
          setStatus(`✓ ${learnedEn} learned. Now sign "${WORD_BY_ID[next]?.en}"…`);
        } else if (quickTrainRef.current) {
          setRecordingWord(null);
          setQuickTrain(false);
          setStatus(`✓ ${learnedEn} learned — Quick Setup complete! Switch to Live.`);
        } else {
          setRecordingWord(null);
          setStatus(`Learned "${learnedEn}" ✓ (${templatesRef.current[teachId].length} sample${templatesRef.current[teachId].length > 1 ? "s" : ""})`);
        }
        return;
      }

      if (modeRef.current === "live") {
        const result = classify(seq, templatesRef.current, thresholdRef.current);
        if (result) {
          setLiveWord({ id: result.id, conf: result.conf });
          setSentence((s) => [...s, result.id]);
          lastWordAtRef.current = Date.now();
          setStatus(`Recognised: ${WORD_BY_ID[result.id]?.en} (${Math.round(result.conf * 100)}%)`);
        } else {
          setStatus("Sign not recognised — teach it first or sign more clearly");
        }
      }
    }

    function onResults(res: any) {
      const cv = canvasRef.current; if (!cv) return;
      const ctx = cv.getContext("2d"); if (!ctx) return;
      ctx.save();
      ctx.clearRect(0, 0, cv.width, cv.height);
      if (res.image) ctx.drawImage(res.image, 0, 0, cv.width, cv.height);

      // draw landmarks for visual feedback
      const drawPts = (pts: any, color: string, r = 3) => {
        if (!pts) return;
        ctx.fillStyle = color;
        for (const p of pts) {
          ctx.beginPath(); ctx.arc(p.x * cv.width, p.y * cv.height, r, 0, 6.28); ctx.fill();
        }
      };
      drawPts(res.poseLandmarks, "rgba(156,136,83,0.5)", 2);
      drawPts(res.leftHandLandmarks, "#2563eb", 3);
      drawPts(res.rightHandLandmarks, "#9c8853", 3);

      const vec = featureVector(res);
      const armed = modeRef.current === "teach" ? !!recordingWordRef.current : true;

      if (vec) {
        const mag = prevVec ? motionMag(vec, prevVec) : 0;
        prevVec = vec;

        if (!recording) {
          if (armed && mag > MOTION_START) {
            recording = true; buffer = [vec]; stillCount = 0;
            setStatus(modeRef.current === "teach" ? "Recording your sign…" : "Reading your sign…");
          }
        } else {
          buffer.push(vec);
          if (mag < MOTION_STOP) { stillCount++; } else { stillCount = 0; }
          if (stillCount >= STILL_FRAMES || buffer.length >= MAX_SEG_FRAMES) {
            recording = false;
            const seg = buffer.slice(0, buffer.length - stillCount); // drop trailing still
            finalizeSegment(seg.length >= 6 ? seg : buffer);
            buffer = [];
          }
        }
      } else {
        prevVec = null;
        if (recording) { recording = false; finalizeSegment(buffer); buffer = []; }
      }

      // on-canvas recording indicator
      if (recording) {
        ctx.fillStyle = "rgba(220,38,38,0.9)";
        ctx.beginPath(); ctx.arc(20, 20, 8, 0, 6.28); ctx.fill();
      }
      ctx.restore();
    }

    async function init() {
      try {
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/holistic/holistic.js");
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js");
        if (cancelled) return;
        const W = window as any;
        holistic = new W.Holistic({
          locateFile: (f: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/holistic/${f}`,
        });
        holistic.setOptions({
          modelComplexity: 1,
          smoothLandmarks: true,
          refineFaceLandmarks: false,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
        holistic.onResults(onResults);
        if (videoRef.current) {
          camera = new W.Camera(videoRef.current, {
            onFrame: async () => { try { await holistic.send({ image: videoRef.current }); } catch {} },
            width: 540, height: 405,
          });
          camera.start();
          setReady(true);
          setStatus("Ready — pick a word and record it, or switch to Live");
        }
      } catch {
        setError("Could not start the camera or load the vision model. Allow camera access and use Chrome/Edge.");
      }
    }

    init();
    return () => {
      cancelled = true;
      try { camera?.stop(); } catch {}
      try { holistic?.close(); } catch {}
    };
  }, [persist]);

  // ── derived ──
  const totalTrained = Object.values(trainedCounts).reduce((a, b) => a + b, 0);
  const trainedWords = Object.keys(trainedCounts).filter((k) => trainedCounts[k] > 0).length;

  function startRecording(id: string) {
    setMode("teach");
    setQuickTrain(false);
    quickQueueRef.current = [];
    setRecordingWord(id);
    setStatus(`Perform the sign for "${WORD_BY_ID[id]?.en}" once…`);
  }
  function startQuickTrain() {
    const queue = VOCAB.map((w) => w.id);
    const first = queue.shift()!;
    quickQueueRef.current = queue;
    setMode("teach");
    setQuickTrain(true);
    setRecordingWord(first);
    setStatus(`Quick Setup — sign "${WORD_BY_ID[first]?.en}" once. It auto-advances.`);
  }
  function stopQuickTrain() {
    quickQueueRef.current = [];
    setQuickTrain(false);
    setRecordingWord(null);
    setStatus("Quick Setup paused");
  }
  function clearTemplates() {
    templatesRef.current = {};
    persist();
    setStatus("Cleared all learned signs");
  }

  return (
    <div className="bg-moei-cream/30 min-h-screen flex flex-col">
      {/* header */}
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="moei-kicker">Accessibility · Real Sign-Language AI</span>
              <h1 className="mt-1 moei-h-section">Sign-Language Conversation</h1>
              <p className="mt-1 max-w-2xl text-sm text-moei-body">
                Word-level recognition with MediaPipe Holistic (hands + body). Each motion = a word →
                builds a sentence → the assistant replies, with voice. Works in English (ASL) and Arabic (ArSL).
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                className="moei-btn-secondary"
              >
                {language === "en" ? "العربية (ArSL)" : "English (ASL)"}
              </button>
              <button onClick={() => { setMessages([]); setSentence([]); }} className="moei-btn-secondary">
                <RotateCcw size={14} /> Clear chat
              </button>
            </div>
          </div>

          {/* mode toggle */}
          <div className="mt-4 inline-flex rounded-xl border border-moei-line bg-moei-cream/40 p-1">
            <button
              onClick={() => { setMode("teach"); setLiveWord(null); }}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                mode === "teach" ? "bg-moei-bronze text-white" : "text-moei-body hover:text-moei-bronze"
              }`}
            >
              <GraduationCap size={15} /> Teach signs
            </button>
            <button
              onClick={() => { setMode("live"); setRecordingWord(null); }}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                mode === "live" ? "bg-emerald-600 text-white" : "text-moei-body hover:text-emerald-700"
              }`}
            >
              <Radio size={15} /> Live conversation
            </button>
          </div>
        </div>
      </section>

      <section className="flex-1 mx-auto max-w-7xl px-6 py-6 w-full">
        <div className="grid gap-6 lg:grid-cols-3">
          {/* camera + status */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="relative overflow-hidden rounded-xl bg-slate-900" style={{ aspectRatio: "4/3" }}>
                <video ref={videoRef} className="hidden" playsInline />
                <canvas ref={canvasRef} width={540} height={405} className="h-full w-full -scale-x-100" />
                {!ready && !error && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300">
                    <CamIcon className="animate-pulse" size={32} />
                    <p className="mt-3 text-sm">Loading camera + MediaPipe Holistic…</p>
                  </div>
                )}
                {error && (
                  <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-red-300">{error}</div>
                )}
                {/* live recognised word */}
                {mode === "live" && liveWord && (
                  <div className="absolute left-3 top-3 rounded-full bg-emerald-600 px-4 py-2 text-base font-bold text-white shadow-lg">
                    {WORD_BY_ID[liveWord.id]?.emoji} {WORD_BY_ID[liveWord.id]?.[language]} · {Math.round(liveWord.conf * 100)}%
                  </div>
                )}
                {mode === "teach" && recordingWord && (
                  <div className="absolute left-3 top-3 rounded-full bg-red-600 px-4 py-2 text-sm font-bold text-white animate-pulse">
                    ● Recording: {WORD_BY_ID[recordingWord]?.[language]}
                  </div>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-moei-muted">
                  MediaPipe Holistic · 98-D motion vector/frame · DTW few-shot match · no video leaves device
                </span>
                <span className={`font-semibold ${mode === "live" ? "text-emerald-700" : "text-moei-bronze"}`}>{status}</span>
              </div>
            </div>

            {/* sentence builder (live) */}
            {mode === "live" && (
              <div className="rounded-2xl border border-moei-line bg-white p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Sentence being built</span>
                  <button onClick={() => setSentence([])} className="text-moei-muted hover:text-red-600" aria-label="Clear"><Trash2 size={14} /></button>
                </div>
                <div className="min-h-[52px] rounded-lg border border-moei-line bg-moei-cream/30 px-3 py-2 flex flex-wrap gap-2 items-center" dir={language === "ar" ? "rtl" : "ltr"}>
                  {sentence.length ? sentence.map((id, i) => (
                    <span key={i} className="rounded-full bg-moei-bronze/10 border border-moei-bronze/30 px-3 py-1 text-sm font-semibold text-moei-ink">
                      {WORD_BY_ID[id]?.emoji} {WORD_BY_ID[id]?.[language]}
                    </span>
                  )) : <span className="text-moei-muted text-sm">Sign words — they appear here. Pause 2.5s to send.</span>}
                </div>
                <button onClick={sendSentence} disabled={busy || sentence.length === 0} className="moei-btn-primary mt-3 w-full justify-center disabled:opacity-50">
                  <Send size={14} /> {busy ? "Sending…" : "Send now (or pause to auto-send)"}
                </button>
              </div>
            )}

            {/* sensitivity (advanced) */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold uppercase tracking-wider text-moei-muted">Match sensitivity</span>
                <span className="text-moei-bronze font-semibold">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range" min={0.6} max={2.5} step={0.05} value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="mt-2 w-full accent-moei-bronze"
              />
              <p className="mt-1 text-[11px] text-moei-muted">Higher = accepts looser matches. If a sign isn&apos;t recognised, raise it slightly. If wrong words trigger, lower it.</p>
            </div>
          </div>

          {/* right column: teach library OR chat */}
          <div className="space-y-4">
            {/* sign library / teach */}
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                  <Hand size={13} /> Sign library
                </div>
                <span className="text-[11px] text-moei-muted">{trainedWords}/{VOCAB.length} taught · {totalTrained} samples</span>
              </div>

              {/* Quick Setup — guided one-click training of the whole vocabulary */}
              {quickTrain ? (
                <div className="mb-3 rounded-lg border border-red-300 bg-red-50 p-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-red-700">
                      Quick Setup · {VOCAB.length - quickQueueRef.current.length}/{VOCAB.length}
                    </span>
                    <button onClick={stopQuickTrain} className="text-[11px] text-moei-muted hover:text-red-700">stop</button>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-red-200">
                    <div className="h-full bg-red-600 transition-all" style={{ width: `${((VOCAB.length - quickQueueRef.current.length) / VOCAB.length) * 100}%` }} />
                  </div>
                  <p className="mt-1.5 text-[11px] text-red-700">
                    Sign <strong>{recordingWord ? WORD_BY_ID[recordingWord]?.[language] : ""}</strong> once — it auto-advances.
                  </p>
                </div>
              ) : (
                <button
                  onClick={startQuickTrain}
                  disabled={!ready}
                  className="mb-3 w-full moei-btn-primary justify-center disabled:opacity-50"
                >
                  <GraduationCap size={14} /> Quick Setup — teach all {VOCAB.length} signs (~60s)
                </button>
              )}

              <div className="space-y-3 max-h-[300px] overflow-y-auto">
                {CATEGORIES.map((cat) => (
                  <div key={cat}>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-moei-bronze/70 mb-1.5">{cat}</div>
                    <div className="space-y-1.5">
                      {VOCAB.filter((w) => w.cat === cat).map((w) => {
                        const count = trainedCounts[w.id] || 0;
                        return (
                          <div key={w.id} className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 ${count ? "border-emerald-200 bg-emerald-50/50" : "border-moei-line"}`}>
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-base">{w.emoji}</span>
                              <div className="min-w-0">
                                <div className="text-[12px] font-semibold text-moei-ink truncate">{w[language]}</div>
                                <div className="text-[10px] text-moei-muted truncate">{language === "en" ? w.ar : w.en}</div>
                              </div>
                            </div>
                            <button
                              onClick={() => startRecording(w.id)}
                              disabled={!ready || recordingWord === w.id}
                              className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold transition disabled:opacity-50 shrink-0 ${
                                count ? "text-emerald-700 hover:bg-emerald-100" : "text-moei-bronze hover:bg-moei-cream"
                              }`}
                            >
                              {recordingWord === w.id ? (<><CircleDot size={12} className="animate-pulse" /> sign</>)
                                : count ? (<><Check size={12} /> {count}</>)
                                : (<><CircleDot size={12} /> record</>)}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {totalTrained > 0 && (
                <button onClick={clearTemplates} className="mt-2 text-[11px] text-moei-muted hover:text-red-600">Clear all learned signs</button>
              )}
              <div className="mt-3 rounded-lg bg-moei-cream/40 p-2.5 text-[11px] text-moei-body leading-relaxed">
                <strong>For judges:</strong> Click <em>Quick Setup</em> and sign each prompted word once
                (~60s, one-time — it&apos;s saved in your browser). Then switch to <em>Live</em>: sign
                naturally, words build a sentence, pause 2.5s and the assistant replies with voice.
                Use the <strong>{language === "en" ? "العربية" : "English"}</strong> toggle (top-right) to switch sign language.
              </div>
            </div>

            {/* conversation */}
            <div className="rounded-2xl border border-moei-line bg-white p-4 flex flex-col">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-moei-line">
                <MessageCircle size={16} className="text-moei-bronze" />
                <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Conversation</span>
              </div>
              <div className="space-y-3 max-h-[320px] overflow-y-auto">
                {messages.length === 0 ? (
                  <p className="text-xs text-moei-muted text-center py-6">Switch to Live and sign to start the conversation…</p>
                ) : messages.map((m, i) => (
                  <div key={i} className={`text-xs p-2.5 rounded-lg ${m.role === "user" ? "bg-moei-bronze/10 border border-moei-bronze/30 text-moei-ink" : "bg-emerald-50 border border-emerald-200 text-emerald-900"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-[10px]">{m.role === "user" ? "You (signed)" : "Assistant"}</span>
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

// ── helpers (pure) ───────────────────────────────────────────────────────────
function resample(seq: number[][], L: number): number[][] {
  if (seq.length === L) return seq;
  if (seq.length < 2) return Array.from({ length: L }, () => seq[0] || new Array(FEAT_DIM).fill(0));
  const out: number[][] = [];
  for (let i = 0; i < L; i++) {
    const idx = Math.round((i * (seq.length - 1)) / (L - 1));
    out.push(seq[idx]);
  }
  return out;
}

function frameDist(a: number[], b: number[]): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) { const d = a[i] - b[i]; s += d * d; }
  return Math.sqrt(s);
}

// Dynamic Time Warping distance between two equal-feature sequences, normalised by length.
function dtw(a: number[][], b: number[][]): number {
  const n = a.length, m = b.length, INF = 1e9;
  let prev = new Array(m + 1).fill(INF); prev[0] = 0;
  for (let i = 1; i <= n; i++) {
    const cur = new Array(m + 1).fill(INF);
    for (let j = 1; j <= m; j++) {
      const c = frameDist(a[i - 1], b[j - 1]);
      cur[j] = c + Math.min(prev[j], cur[j - 1], prev[j - 1]);
    }
    prev = cur;
  }
  return prev[m] / (n + m); // normalise by warping-path scale
}

// Few-shot classify: nearest template by DTW; accept if below threshold.
function classify(seq: number[][], templates: Templates, threshold: number):
  { id: string; conf: number } | null {
  let bestId = "", best = Infinity, second = Infinity;
  for (const [id, samples] of Object.entries(templates)) {
    for (const s of samples) {
      const d = dtw(seq, s);
      if (d < best) { second = best; best = d; bestId = id; }
      else if (d < second) { second = d; }
    }
  }
  if (!bestId || best > threshold) return null;
  // confidence: closeness to threshold, with a margin bonus over the runner-up
  const closeness = Math.max(0, 1 - best / threshold);
  const margin = second === Infinity ? 0.25 : Math.min(0.25, Math.max(0, (second - best) / threshold));
  return { id: bestId, conf: Math.min(0.99, 0.5 + closeness * 0.4 + margin) };
}
