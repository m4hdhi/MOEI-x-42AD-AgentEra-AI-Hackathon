"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Sparkles, FileText, User, Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import { DocumentUpload } from "@/components/DocumentUpload";
import type { UaePassSession } from "@/lib/auth";

type Msg = {
  role: "user" | "assistant";
  text: string;
  lang?: string;
  service?: string;
  intent?: string;
  confidence?: number;
  escalated?: boolean;
  sentiment?: number;
  nextBestAction?: string;
  suggestedReplies?: string[];
  citations?: { title: string; url: string; source?: string }[];
  escalationRisk?: { risk: number; band: string; factors: string[]; model: string };
  correlationId?: string;
  streaming?: boolean;
};

// Browser SpeechRecognition is vendor-prefixed
type SpeechRec = any;

const PROMPTS = [
  "I'm 4 months behind on my SZHP loan, my salary is 20000 AED, balance is 150000",
  "أحتاج تأجيل قسط السكن، راتبي 20000 درهم والرصيد 150000",
  "How do I report a power outage?",
  "What documents do I need to apply for SZHP?",
  "I want to renew my pleasure boat registration",
  "Connect me with a human agent",
];

export default function ChatPage() {
  return (
    <LoginGate
      title="Sign in to chat with the MOEI Smart Assistant"
      subtitle="Signing in lets us recognise you, keep your conversation history, and create service requests on your behalf."
    >
      {(session) => <ChatExperience session={session} />}
    </LoginGate>
  );
}

function ChatExperience({ session: uaepassSession }: { session: UaePassSession }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const recogRef = useRef<SpeechRec | null>(null);

  // Admin debug view — citizens see clean replies, staff with ?admin=1 see meta + NBA.
  const [adminMode, setAdminMode] = useState(false);
  useEffect(() => {
    try { setAdminMode(new URLSearchParams(window.location.search).get("admin") === "1"); } catch {}
  }, []);

  // Verified identity from UAE PASS (the gate guarantees we're authenticated here).
  const userId = uaepassSession.emirates_id || "anonymous";
  const userName = uaepassSession.full_name_en || "Citizen";

  // Hyper-personalized recommendations for this citizen.
  const [recs, setRecs] = useState<{ title: string; reason: string; action: string; href: string }[]>([]);
  useEffect(() => {
    fetch(`${API_URL}/crm/citizens/${encodeURIComponent(userId)}/recommendations`)
      .then((r) => r.json()).then((d) => setRecs(d.recommendations || [])).catch(() => {});
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Init browser speech recognition once
  useEffect(() => {
    if (typeof window === "undefined") return;
    const SR =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setSpeechSupported(false);
      return;
    }
    setSpeechSupported(true);
    const r = new SR();
    r.continuous = false;
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.lang = "en-US"; // updated dynamically when user speaks Arabic
    r.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      setListening(false);
      send(transcript, /*viaVoice=*/ true);
    };
    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);
    recogRef.current = r;
  }, []);

  const startListening = useCallback(() => {
    const r = recogRef.current;
    if (!r) return;
    try {
      // Best-effort multilingual: alternate Arabic/English by recent input
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      r.lang = /[؀-ۿ]/.test(lastUser?.text ?? "") ? "ar-AE" : "en-US";
      r.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [messages]);

  const speak = useCallback((text: string, lang?: string) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = lang === "ar" ? "ar-AE" : "en-US";
    utter.rate = 1.05;
    utter.pitch = 1.0;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }, []);

  async function send(textOverride?: string, viaVoice = false) {
    const text = (textOverride ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);

    setMessages((m) => [...m, { role: "assistant", text: "", streaming: true }]);

    // Hard abort if the whole turn takes longer than 75s — never let the UI freeze.
    const controller = new AbortController();
    const hardTimeout = setTimeout(() => controller.abort(), 75_000);

    // After 10s with no token, show a "taking longer than usual" hint
    const slowTimer = setTimeout(() => {
      setMessages((m) => {
        const next = [...m];
        const last = next[next.length - 1];
        if (last?.streaming && !last.text) {
          next[next.length - 1] = {
            ...last,
            text: "This is taking a moment. Please hold on.",
          };
        }
        return next;
      });
    }, 10_000);

    try {
      const endpoint = viaVoice ? "/voice/turn" : "/chat/web/stream";
      if (!viaVoice) {
        // Streaming path — Server-Sent Events
        const res = await fetch(`${API_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          signal: controller.signal,
          body: JSON.stringify({
            user_id: userId,
            channel: "web",
            session_id: sessionId,
            language: "auto",
            text,
          }),
        });
        if (!res.body) throw new Error("no stream body");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const evt = JSON.parse(line.slice(6));
              if (evt.event === "token") {
                // First token cancels the "taking longer" hint
                clearTimeout(slowTimer);
                if (!accumulated) {
                  // Wipe the "thinking" placeholder before appending real text
                  setMessages((m) => {
                    const next = [...m];
                    next[next.length - 1] = { ...next[next.length - 1], text: "" };
                    return next;
                  });
                }
                accumulated += evt.delta;
                setMessages((m) => {
                  const next = [...m];
                  next[next.length - 1] = { ...next[next.length - 1], text: accumulated };
                  return next;
                });
              } else if (evt.event === "reply") {
                setMessages((m) => {
                  const next = [...m];
                  next[next.length - 1] = {
                    role: "assistant",
                    text: evt.text,
                    lang: evt.language,
                    service: evt.service,
                    intent: evt.intent,
                    confidence: evt.confidence,
                    escalated: evt.escalated,
                    sentiment: evt.sentiment,
                    nextBestAction: evt.next_best_action,
                    suggestedReplies: evt.suggested_replies ?? [],
                    citations: evt.citations ?? [],
                    escalationRisk: evt.escalation_risk ?? undefined,
                    correlationId: evt.correlation_id,
                    streaming: false,
                  };
                  return next;
                });
              }
            } catch {
              // ignore bad chunk
            }
          }
        }
      } else {
        // Voice fallback: regular JSON, then speak the reply
        const res = await fetch(`${API_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            user_id: userId,
            channel: "voice",
            session_id: sessionId,
            language: "auto",
            text,
          }),
        });
        const data = await res.json();
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = {
            role: "assistant",
            text: data.text,
            lang: data.language,
            service: data.service,
            intent: data.intent,
            confidence: data.confidence,
            escalated: data.escalated,
            suggestedReplies: data.suggested_replies ?? [],
            citations: data.citations ?? [],
            escalationRisk: data.escalation_risk ?? undefined,
            correlationId: data.correlation_id,
            streaming: false,
          };
          return next;
        });
        if (voiceMode) speak(data.text, data.language);
      }
    } catch (e: any) {
      const isAbort = e?.name === "AbortError" || String(e).includes("aborted");
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = {
          role: "assistant",
          text: isAbort
            ? "We could not process that just now. Please rephrase, or call 800 6634 for immediate help."
            : `Connection error: ${String(e)}`,
          streaming: false,
        };
        return next;
      });
    } finally {
      clearTimeout(hardTimeout);
      clearTimeout(slowTimer);
      setBusy(false);
    }
  }

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <span className="moei-kicker">MOEI Smart Assistant</span>
          <h1 className="mt-3 moei-h-section">How can we help today?</h1>
          <p className="mt-3 max-w-2xl text-moei-body">
            Ask about housing, energy, transport, maritime, or infrastructure
            services. Type your question or tap the microphone to speak.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <div className="grid gap-6 lg:grid-cols-12">
          {/* Main chat panel */}
          <div className="lg:col-span-8">
            <div className="moei-card overflow-hidden">
              <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
                <div className="flex items-center gap-2 text-sm">
                  <span className="flex h-2 w-2 rounded-full bg-moei-bronze" />
                  <span className="font-semibold text-moei-ink">MOEI Smart Assistant</span>
                  <span className="text-moei-muted">· Customer Happiness Centre</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setVoiceMode((v) => !v)}
                    title={voiceMode ? "Mute voice replies" : "Hear voice replies"}
                    className={
                      "moei-btn-icon h-8 w-8 " +
                      (voiceMode ? "border-moei-bronze text-moei-bronze" : "")
                    }
                  >
                    {voiceMode ? <Volume2 size={14} /> : <VolumeX size={14} />}
                  </button>
                  <span className="text-[11px] uppercase tracking-wider text-moei-muted">
                    Session {sessionId.slice(0, 8)}
                  </span>
                </div>
              </div>

              <div className="h-[480px] overflow-y-auto px-5 py-6">
                {messages.length === 0 && (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <Sparkles className="text-moei-bronze" size={28} />
                    <p className="mt-3 max-w-md text-sm text-moei-body">
                      Welcome back{userName ? `, ${userName.split(" ")[0]}` : ""}. Type a question, tap{" "}
                      <Mic className="inline -mt-0.5" size={14} /> to speak, or pick a suggestion.
                    </p>
                    {recs.length > 0 && (
                      <div className="mt-5 w-full max-w-md">
                        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-moei-bronze">
                          Recommended for you
                        </div>
                        <div className="space-y-2">
                          {recs.map((r, i) => (
                            <button
                              key={i}
                              onClick={() => send(r.title)}
                              className="flex w-full items-center justify-between gap-3 rounded-xl border border-moei-line bg-white px-3 py-2 text-left transition hover:border-moei-bronze"
                            >
                              <span>
                                <span className="block text-sm font-medium text-moei-ink">{r.title}</span>
                                <span className="block text-[11px] text-moei-muted">{r.reason}</span>
                              </span>
                              <span className="shrink-0 text-[11px] font-semibold text-moei-bronze">{r.action} →</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <div className="space-y-4">
                  {messages.map((m, i) => (
                    <Bubble key={i} m={m} onPickReply={(r) => send(r)} adminMode={adminMode} />
                  ))}
                  <div ref={bottomRef} />
                </div>
              </div>

              <div className="border-t border-moei-line p-4">
                <div className="flex items-center gap-2">
                  {speechSupported && (
                    <button
                      onClick={startListening}
                      disabled={busy || listening}
                      title={listening ? "Listening…" : "Speak instead of typing"}
                      className={
                        "moei-btn-icon " +
                        (listening
                          ? "animate-pulse border-red-400 text-red-500"
                          : "")
                      }
                    >
                      {listening ? <MicOff size={16} /> : <Mic size={16} />}
                    </button>
                  )}
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && send()}
                    placeholder="Ask in English or Arabic…"
                    className="flex-1 rounded-full border border-moei-line bg-white px-5 py-3 text-sm outline-none focus:border-moei-bronze"
                  />
                  <button onClick={() => send()} disabled={busy} className="moei-btn-primary">
                    <Send size={14} /> Send
                  </button>
                </div>
                {!speechSupported && (
                  <p className="mt-2 text-[11px] text-moei-muted">
                    The voice button works in Chrome and Edge. On Safari, please type your question.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Side panel */}
          <aside className="space-y-4 lg:col-span-4">
            <div className="moei-card p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-moei-cream">
                  <User className="text-moei-bronze" size={20} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-moei-ink">{userName}</div>
                  <div className="text-xs text-moei-muted">
                    UAE PASS verified · {uaepassSession.user_type ?? "SOP2"}
                  </div>
                </div>
              </div>
              <dl className="mt-4 space-y-1.5 text-xs">
                {[
                  ["Emirates ID", userId],
                  ["Mobile", uaepassSession.mobile ?? "—"],
                  ["Email", uaepassSession.email ?? "—"],
                  ["Nationality", uaepassSession.nationality_en ?? "UAE"],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="flex justify-between border-b border-moei-line/60 pb-1.5"
                  >
                    <dt className="text-moei-muted">{k}</dt>
                    <dd className="font-medium text-moei-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="moei-card p-5">
              <div className="moei-kicker">Try a prompt</div>
              <ul className="mt-3 space-y-2">
                {PROMPTS.map((p) => (
                  <li key={p}>
                    <button
                      onClick={() => send(p)}
                      disabled={busy}
                      dir={/[؀-ۿ]/.test(p) ? "rtl" : "ltr"}
                      className="w-full rounded-xl border border-moei-line px-3 py-2 text-left text-sm text-moei-body transition hover:border-moei-bronze hover:text-moei-bronze"
                    >
                      {p}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <DocumentUpload />

            <div className="rounded-2xl border border-moei-bronze/40 bg-moei-cream/50 p-5 text-xs text-moei-body">
              <div className="flex items-center gap-2 font-semibold text-moei-ink">
                <FileText size={14} /> Need to speak to a person?
              </div>
              <p className="mt-2 leading-relaxed">
                You can ask for a human agent at any time, or call our Customer
                Happiness Centre on <span className="font-semibold text-moei-bronze">800 6634</span>{" "}
                — available 24 hours a day, every day of the week.
              </p>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

function Bubble({ m, onPickReply, adminMode }: { m: Msg; onPickReply: (r: string) => void; adminMode: boolean }) {
  const isUser = m.role === "user";
  const isArabic = m.lang === "ar" || /[؀-ۿ]/.test(m.text);
  // If we have structured citations, strip the inline "More info" markdown footer from the
  // text so the bubble stays clean — citizens get the citations as pretty pills below.
  const hasCitations = !!(m.citations && m.citations.length);
  const displayText = hasCitations
    ? m.text.replace(/\n+\*\*(?:More info|أكثر):\*\*.*$/s, "").trim()
    : m.text;
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className={"max-w-[85%] " + (isUser ? "" : "w-full")}>
        <div
          dir={isArabic ? "rtl" : "ltr"}
          className={
            "whitespace-pre-line px-4 py-3 text-sm " +
            (isUser
              ? "rounded-2xl rounded-br-md bg-moei-ink text-white"
              : "rounded-2xl rounded-bl-md border border-moei-line bg-white text-moei-ink")
          }
        >
          {displayText || (m.streaming ? "…" : "")}
        </div>

        {!isUser && !m.streaming && hasCitations && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
              {isArabic ? "أكثر" : "More info"}
            </span>
            {m.citations!.slice(0, 3).map((c) => (
              <a
                key={c.url}
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-full border border-moei-bronze/40 bg-moei-cream/40 px-2.5 py-0.5 text-[11px] font-medium text-moei-bronze transition hover:bg-moei-bronze hover:text-white"
                title={c.url}
              >
                {c.title}
                <span aria-hidden>↗</span>
              </a>
            ))}
          </div>
        )}

        {/* Technical metadata + NBA only shown in admin/staff view.
            Citizens see only the polished reply + suggested replies. */}
        {adminMode && !isUser && !m.streaming && m.service && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
            <Chip label={`service: ${m.service}`} accent={m.service === "housing"} />
            {m.intent && <Chip label={`intent: ${m.intent}`} />}
            {m.confidence !== undefined && (
              <Chip label={`confidence: ${(m.confidence * 100).toFixed(0)}%`} />
            )}
            {m.sentiment !== undefined && m.sentiment !== null && (
              <Chip
                label={`sentiment: ${(m.sentiment * 100).toFixed(0)}%`}
                alert={m.sentiment < 0.4}
                accent={m.sentiment >= 0.7}
              />
            )}
            {m.escalated && <Chip label="ESCALATED → co-pilot" alert />}
            {m.escalationRisk && m.escalationRisk.risk !== undefined && (
              <Chip
                label={`risk: ${(m.escalationRisk.risk * 100).toFixed(0)}% ${m.escalationRisk.band}`}
                alert={m.escalationRisk.band === "high"}
                accent={m.escalationRisk.band === "medium"}
              />
            )}
            {m.correlationId && (
              <a
                href={`/admin/audit?cid=${m.correlationId}`}
                className="ml-auto rounded-full bg-moei-cream px-2 py-0.5 text-moei-bronze hover:bg-moei-bronze hover:text-white"
              >
                Trace →
              </a>
            )}
          </div>
        )}

        {adminMode && !isUser && !m.streaming && m.nextBestAction && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-moei-bronze/30 bg-moei-cream/60 px-3 py-2 text-[11px] text-moei-ink">
            <span className="rounded bg-moei-bronze px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white">
              Co-pilot NBA
            </span>
            <span className="flex-1">{m.nextBestAction}</span>
          </div>
        )}

        {!isUser && !m.streaming && m.suggestedReplies && m.suggestedReplies.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {m.suggestedReplies.slice(0, 3).map((r) => (
              <button
                key={r}
                onClick={() => onPickReply(r)}
                dir={/[؀-ۿ]/.test(r) ? "rtl" : "ltr"}
                className="rounded-full border border-moei-bronze/40 bg-white px-3 py-1 text-[11px] text-moei-bronze transition hover:bg-moei-cream"
              >
                {r}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Chip({ label, accent, alert }: { label: string; accent?: boolean; alert?: boolean }) {
  const cls = alert
    ? "bg-red-50 border border-red-200 text-red-700"
    : accent
    ? "bg-moei-cream border border-moei-bronze/40 text-moei-bronze"
    : "bg-white border border-moei-line text-moei-muted";
  return <span className={"rounded-full px-2 py-0.5 " + cls}>{label}</span>;
}
