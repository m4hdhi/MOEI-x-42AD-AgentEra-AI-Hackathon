"use client";

/**
 * Mobile-app channel (citizen surface).
 *
 * Phone-frame UI that talks to the same assistant with channel="mobile", so the case
 * row + activity event are tagged correctly and cross-channel memory holds. Gated behind
 * UAE PASS sign-in like chat and call, and uses the verified identity.
 */

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft, Send, Sparkles, MoreVertical, Bell, Home, User, Smartphone,
  MessageCircle, Mic, Globe,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

type Msg = {
  role: "user" | "assistant";
  text: string;
  channel?: string;
  citations?: { title: string; url: string }[];
};

const PROMPTS = [
  "Status of my housing application",
  "Renew my boat registration",
  "Report a power outage in my area",
];

// Small label + icon for messages that arrived on another channel (cross-channel continuity).
const CHANNEL_META: Record<string, { label: string; Icon: typeof Globe }> = {
  whatsapp: { label: "WhatsApp", Icon: MessageCircle },
  voice: { label: "Call", Icon: Mic },
  web: { label: "Web", Icon: Globe },
  mobile: { label: "App", Icon: Smartphone },
};

export default function MobilePage() {
  return (
    <LoginGate
      title="Sign in to use the MOEI Smart App"
      subtitle="Sign in with UAE PASS so we can recognise you and keep your requests in one place across every channel."
    >
      {(session) => <MobileExperience session={session} />}
    </LoginGate>
  );
}

function MobileExperience({ session }: { session: UaePassSession }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [resumed, setResumed] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const userId = session.emirates_id || "anonymous";
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Resume the conversation: pull the customer's recent turns from EVERY channel so the
  // thread continues where they left off (WhatsApp / call / web), not a blank screen.
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_URL}/chat/history?n=20`, { credentials: "include" });
        const d = await r.json();
        const turns: Msg[] = (d.turns || []).map((t: any) => ({
          role: t.role, text: t.text, channel: t.channel,
        }));
        if (turns.length) {
          setMessages(turns);
          setResumed(turns.some((t) => t.channel && t.channel !== "mobile"));
        }
      } catch { /* offline-safe */ }
    })();
  }, []);

  async function send(textOverride?: string) {
    const text = (textOverride ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text, channel: "mobile" }]);
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/chat/web`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: userId,
          channel: "mobile",
          session_id: sessionId,
          language: "auto",
          text,
        }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", text: data.text, channel: "mobile", citations: data.citations ?? [] },
      ]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Connection error: ${String(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-moei-cream/30 py-12">
      <div className="mx-auto max-w-md">
        <div className="mb-4 text-center">
          <span className="moei-kicker">MOEI Mobile App</span>
          <h1 className="mt-1 moei-h-section text-3xl">MOEI Smart App</h1>
          <p className="mt-1 text-xs text-moei-muted">
            All your ministry services in your pocket.
          </p>
        </div>

        {/* Phone frame */}
        <div className="rounded-[44px] border-[12px] border-moei-ink bg-white p-1 shadow-2xl">
          <div className="overflow-hidden rounded-[34px] bg-white">
            {/* Status bar */}
            <div className="flex items-center justify-between bg-moei-ink px-5 py-2 text-[10px] text-white">
              <span>9:41</span>
              <span className="flex items-center gap-1">
                <span>5G</span><span>•••</span><span>100%</span>
              </span>
            </div>
            {/* App bar */}
            <div className="flex items-center justify-between border-b border-moei-line bg-white px-4 py-2.5">
              <button className="text-moei-muted hover:text-moei-ink" aria-label="Back"><ArrowLeft size={18} /></button>
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-moei-bronze to-moei-bronze-dark shadow-sm">
                  <Sparkles size={16} className="text-white" />
                </span>
                <div className="leading-tight">
                  <div className="flex items-center gap-1.5 text-[13px] font-bold text-moei-ink">
                    Smart Assistant
                    <span className="flex items-center gap-0.5 rounded-full bg-emerald-50 px-1.5 py-px text-[8px] font-semibold text-emerald-600">
                      <span className="h-1 w-1 rounded-full bg-emerald-500" /> Online
                    </span>
                  </div>
                  <div className="text-[9px] text-moei-muted">Ministry of Energy &amp; Infrastructure</div>
                </div>
              </div>
              <button className="text-moei-muted hover:text-moei-ink" aria-label="Menu"><MoreVertical size={18} /></button>
            </div>

            {/* Chat area */}
            <div className="h-[460px] overflow-y-auto bg-moei-cream/20 px-3 py-4">
              {messages.length === 0 && (
                <div className="px-2 pt-6 text-center">
                  <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-moei-bronze to-moei-bronze-dark shadow-md">
                    <Sparkles className="text-white" size={24} />
                  </span>
                  <p className="mt-3 text-sm font-semibold text-moei-ink">
                    Hello{session.first_name_en ? `, ${session.first_name_en}` : ""} 👋
                  </p>
                  <p className="mt-1 text-xs text-moei-muted">
                    How can I help with your ministry services today?
                  </p>
                  <div className="mt-4 space-y-2">
                    {PROMPTS.map((p) => (
                      <button
                        key={p}
                        onClick={() => send(p)}
                        className="block w-full rounded-2xl border border-moei-line bg-white px-3 py-2.5 text-left text-[12px] text-moei-body shadow-sm transition hover:border-moei-bronze hover:bg-moei-cream/30"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Cross-channel resume banner */}
              {resumed && messages.length > 0 && (
                <div className="mx-2 mb-3 flex items-center justify-center gap-1.5 rounded-full bg-moei-cream/60 px-3 py-1.5 text-[10px] text-moei-bronze">
                  <Sparkles size={11} /> Continuing your conversation across channels
                </div>
              )}
              <div className="space-y-2">
                {messages.map((m, i) => {
                  const hasCit = !!(m.citations && m.citations.length);
                  const cleanText = hasCit
                    ? m.text.replace(/\n+\*\*(?:More info|أكثر):\*\*.*$/s, "").trim()
                    : m.text;
                  const otherChannel = m.channel && m.channel !== "mobile" ? CHANNEL_META[m.channel] : null;
                  return (
                    <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                      <div className="max-w-[80%]">
                        {otherChannel && (
                          <div className={"mb-0.5 flex items-center gap-1 text-[9px] text-moei-muted " + (m.role === "user" ? "justify-end" : "justify-start")}>
                            <otherChannel.Icon size={9} /> via {otherChannel.label}
                          </div>
                        )}
                        <div
                          dir={/[؀-ۿ]/.test(m.text) ? "rtl" : "ltr"}
                          className={
                            "whitespace-pre-line px-3 py-2 text-[12px] " +
                            (m.role === "user"
                              ? "rounded-2xl rounded-br-md bg-moei-bronze text-white"
                              : "rounded-2xl rounded-bl-md border border-moei-line bg-white text-moei-ink")
                          }
                        >
                          {cleanText}
                        </div>
                        {m.role === "assistant" && hasCit && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {m.citations!.slice(0, 2).map((c) => (
                              <a
                                key={c.url}
                                href={c.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-0.5 rounded-full border border-moei-bronze/40 bg-moei-cream/40 px-2 py-0.5 text-[10px] font-medium text-moei-bronze"
                              >
                                {c.title} ↗
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                {busy && <div className="text-center text-[11px] text-moei-muted">One moment…</div>}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Input */}
            <div className="flex items-center gap-2 border-t border-moei-line bg-white px-3 py-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Type your question…"
                className="flex-1 rounded-full border border-moei-line bg-moei-cream/30 px-3 py-2 text-[12px] outline-none focus:border-moei-bronze"
              />
              <button
                onClick={() => send()}
                disabled={busy}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-moei-bronze text-white disabled:opacity-50"
              >
                <Send size={14} />
              </button>
            </div>

            {/* Bottom nav (cosmetic) */}
            <div className="flex items-center justify-around border-t border-moei-line bg-white px-4 py-2">
              <Tab icon={Home} label="Home" />
              <Tab icon={Bell} label="Alerts" />
              <Tab icon={Sparkles} label="Assistant" active />
              <Tab icon={User} label="Account" />
            </div>
          </div>
        </div>

        <p className="mt-4 text-center text-[10px] text-moei-muted">
          Your conversation continues seamlessly across web, WhatsApp, voice, and mobile.
        </p>
      </div>
    </div>
  );
}

function Tab({ icon: Icon, label, active }: { icon: typeof Home; label: string; active?: boolean }) {
  return (
    <div className={"flex flex-col items-center gap-0.5 " + (active ? "text-moei-bronze" : "text-moei-muted")}>
      <Icon size={16} />
      <span className="text-[9px] font-medium">{label}</span>
    </div>
  );
}
