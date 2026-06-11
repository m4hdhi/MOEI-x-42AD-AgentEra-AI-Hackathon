"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Home,
  Keyboard,
  Loader2,
  Mic,
  MicOff,
  Send,
  Sparkles,
} from "lucide-react";
import { LoginGate } from "@/components/LoginGate";
import {
  AUTOMATION_EXAMPLES,
  requestAutomationPlan,
  isArabicText,
  type AutomationPlan,
  type TaskMode,
} from "@/lib/automation";
import type { UaePassSession } from "@/lib/auth";

type SpeechRec = any;
type TalkTurn = { role: "agent" | "user"; text: string };

export default function AutomationPage() {
  return (
    <LoginGate
      title="Sign in to use Task Automation"
      subtitle="The assistant can open the right service and carry your request into the form using your UAE PASS identity."
    >
      {(session) => <AutomationExperience session={session} />}
    </LoginGate>
  );
}

function AutomationExperience({ session }: { session: UaePassSession }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [request, setRequest] = useState("");
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [message, setMessage] = useState("");
  const [plan, setPlan] = useState<AutomationPlan | null>(null);
  const [opening, setOpening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [details, setDetails] = useState<Record<string, string>>({});
  const [planMode, setPlanMode] = useState<TaskMode>("text");
  const [siriMode, setSiriMode] = useState(false);
  const [activeFieldKey, setActiveFieldKey] = useState<string | null>(null);
  const [conversation, setConversation] = useState<TalkTurn[]>([]);
  const recogRef = useRef<SpeechRec | null>(null);
  const redirectRef = useRef<number | null>(null);
  const captureModeRef = useRef<"task" | "detail">("task");
  const activeFieldKeyRef = useRef<string | null>(null);
  const handleRequestRef = useRef<(text: string, mode: TaskMode) => void | Promise<void>>(() => {});
  const handleDetailSpeechRef = useRef<(fieldKey: string, text: string) => void>(() => {});
  const autoRunRequestRef = useRef("");

  useEffect(() => {
    const incoming = searchParams.get("request") || "";
    if (incoming && incoming !== autoRunRequestRef.current) {
      autoRunRequestRef.current = incoming;
      setRequest(incoming);
      window.setTimeout(() => handleRequestRef.current(incoming, "text"), 100);
    }
  }, [searchParams]);

  useEffect(() => {
    activeFieldKeyRef.current = activeFieldKey;
  }, [activeFieldKey]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setSpeechSupported(false);
      return;
    }
    const r = new SR();
    r.continuous = false;
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.lang = "en-US";
    r.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      setListening(false);
      if (captureModeRef.current === "detail" && activeFieldKeyRef.current) {
        handleDetailSpeechRef.current(activeFieldKeyRef.current, transcript);
      } else {
        handleRequestRef.current(transcript, "voice");
      }
    };
    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);
    recogRef.current = r;
    setSpeechSupported(true);
  }, []);

  useEffect(() => {
    return () => {
      if (redirectRef.current) window.clearTimeout(redirectRef.current);
    };
  }, []);

  const speak = useCallback((text: string, lang: "ar" | "en") => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = lang === "ar" ? "ar-AE" : "en-US";
    utter.rate = 1.02;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }, []);

  function startListening(mode: "task" | "detail" = "task", fieldKey?: string) {
    const r = recogRef.current;
    if (!r) return;
    try {
      captureModeRef.current = mode;
      activeFieldKeyRef.current = fieldKey || null;
      if (fieldKey) setActiveFieldKey(fieldKey);
      r.lang = isArabicText(request) ? "ar-AE" : "en-US";
      r.start();
      setListening(true);
      setMessage("Listening...");
    } catch {
      setListening(false);
    }
  }

  function say(text: string, lang: "ar" | "en" = isArabicText(request) ? "ar" : "en") {
    setMessage(text);
    setConversation((turns) => [...turns, { role: "agent", text }]);
    speak(text, lang);
  }

  function nextMissingField(nextPlan: AutomationPlan | null, nextDetails: Record<string, string>) {
    return nextPlan?.required_fields.find((field) => field.required && !String(nextDetails[field.key] || "").trim()) || null;
  }

  function askForField(field: AutomationPlan["required_fields"][number]) {
    const prompt = `Please tell me ${field.label}.`;
    setActiveFieldKey(field.key);
    say(prompt);
    window.setTimeout(() => startListening("detail", field.key), 800);
  }

  function startAssistant() {
    setSiriMode(true);
    setPlan(null);
    setDetails({});
    setConversation([]);
    setActiveFieldKey(null);
    const prompt = "What would you like me to do?";
    say(prompt, "en");
    window.setTimeout(() => startListening("task"), 800);
  }

  function openPlan(nextPlan: AutomationPlan, mode: TaskMode, originalText: string) {
    if (!nextPlan.route) return;
    setOpening(true);
    const lang = isArabicText(originalText) ? "ar" : "en";
    if (mode === "voice") {
      speak(
        lang === "ar"
          ? "تم العثور على سير العمل المناسب. سأفتحه الآن."
          : "I found the right workflow. Opening it now.",
        lang,
      );
    }
    redirectRef.current = window.setTimeout(() => router.push(nextPlan.route!), 900);
  }

  async function handleRequest(text: string, mode: TaskMode) {
    const clean = text.trim();
    if (!clean || opening || busy) return;
    setRequest(clean);
    setConversation((turns) => [...turns, { role: "user", text: clean }]);
    setPlanMode(mode);
    setPlan(null);
    setDetails({});
    setBusy(true);
    setMessage("Agent42 is planning the service action...");
    try {
      const nextPlan = await requestAutomationPlan(clean, mode);
      setPlan(nextPlan);
      setMessage(nextPlan.reply);
      if (mode === "voice" || siriMode) {
        setConversation((turns) => [...turns, { role: "agent", text: nextPlan.reply }]);
        speak(nextPlan.reply, nextPlan.language);
      }
      if (nextPlan.route && nextPlan.action === "open_workflow") {
        openPlan(nextPlan, mode, clean);
      } else if ((mode === "voice" || siriMode) && nextPlan.required_fields.length > 0) {
        const firstMissing = nextMissingField(nextPlan, {});
        if (firstMissing) {
          window.setTimeout(() => askForField(firstMissing), 1200);
        }
      }
    } catch (e: any) {
      setMessage(e?.message || "Automation Agent could not plan that request.");
    } finally {
      setBusy(false);
    }
  }

  function handleDetailSpeech(fieldKey: string, text: string) {
    const clean = text.trim();
    if (!clean || !plan) return;
    const nextDetails = { ...details, [fieldKey]: clean };
    setDetails(nextDetails);
    setConversation((turns) => [...turns, { role: "user", text: clean }]);
    const missing = nextMissingField(plan, nextDetails);
    if (missing) {
      askForField(missing);
      return;
    }
    setActiveFieldKey(null);
    say("I have the required details. I am preparing the request now.");
    window.setTimeout(() => submitPreparedRequest(nextDetails), 700);
  }

  async function submitPreparedRequest(overrideDetails?: Record<string, string>) {
    if (!plan || submitting) return;
    const finalDetails = overrideDetails || details;
    const missing = plan.required_fields
      .filter((field) => field.required && !String(finalDetails[field.key] || "").trim())
      .map((field) => field.label);
    if (missing.length) {
      setMessage(`Please provide: ${missing.join(", ")}`);
      return;
    }
    setSubmitting(true);
    setMessage("Preparing the request and creating the tracked case...");
    try {
      const submitted = await requestAutomationPlan(request, planMode, {
        execute: true,
        details: finalDetails,
      });
      setPlan(submitted);
      setMessage(submitted.reply);
      if (siriMode || planMode === "voice") {
        setConversation((turns) => [...turns, { role: "agent", text: submitted.reply }]);
        speak(submitted.reply, submitted.language);
      }
    } catch (e: any) {
      setMessage(e?.message || "Could not create the request.");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    handleRequestRef.current = handleRequest;
    handleDetailSpeechRef.current = handleDetailSpeech;
  });

  return (
    <div className="min-h-screen bg-moei-cream/30 pb-16">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <span className="moei-kicker">Agent42 Service Automation</span>
          <h1 className="mt-3 moei-h-section flex items-center gap-2">
            <Bot className="text-moei-bronze" size={24} /> Task Automation
          </h1>
          <p className="mt-3 max-w-2xl text-moei-body">
            Say or type the service you need. The LLM Automation Agent reads the MOEI catalog,
            chooses a workflow or case action, and carries your request forward.
          </p>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-10 lg:grid-cols-[1fr_360px]">
        <div className="moei-card overflow-hidden">
          <div className="border-b border-moei-line bg-moei-cream/50 px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
              <Sparkles size={16} className="text-moei-bronze" /> Automation request
            </div>
            <div className="mt-1 text-xs text-moei-muted">
              Signed in as {session.full_name_en || "Citizen"} · {session.emirates_id || "UAE PASS"}
            </div>
          </div>

          <div className="space-y-5 p-5">
            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Keyboard size={14} /> Type the task
              </div>
              <div className="flex gap-2">
                <input
                  value={request}
                  onChange={(e) => setRequest(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleRequest(request, "text")}
                  placeholder="Example: renew my pleasure boat registration"
                  className="min-w-0 flex-1 rounded-full border border-moei-line px-5 py-3 text-sm outline-none focus:border-moei-bronze"
                />
                <button
                  onClick={() => handleRequest(request, "text")}
                  disabled={!request.trim() || opening || busy}
                  className="moei-btn-primary"
                >
                  {opening || busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Run
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-moei-line bg-white p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-muted">
                <Mic size={14} /> Voice request
              </div>
              <div className="mb-3 flex flex-wrap gap-2">
                <button
                  onClick={startAssistant}
                  disabled={!speechSupported || listening || opening || busy || submitting}
                  className={
                    "inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-bold transition " +
                    (siriMode
                      ? "bg-emerald-700 text-white shadow-sm"
                      : "bg-moei-bronze text-white hover:bg-moei-ink")
                  }
                >
                  {listening ? <MicOff size={16} /> : <Bot size={16} />}
                  {listening ? "Listening..." : "Start assistant"}
                </button>
                {siriMode && (
                  <button
                    onClick={() => {
                      setSiriMode(false);
                      setActiveFieldKey(null);
                      captureModeRef.current = "task";
                      try { recogRef.current?.stop(); } catch {}
                      window.speechSynthesis?.cancel();
                      setListening(false);
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-moei-line px-4 py-2.5 text-sm font-semibold text-moei-body hover:border-moei-bronze hover:text-moei-bronze"
                  >
                    Stop
                  </button>
                )}
              </div>
              <button
                onClick={() => startListening("task")}
                disabled={!speechSupported || listening || opening || busy}
                className={
                  "inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition " +
                  (listening
                    ? "border-red-300 bg-red-50 text-red-600"
                    : "border-moei-bronze bg-moei-cream/40 text-moei-bronze hover:bg-moei-cream")
                }
              >
                {listening ? <MicOff size={16} /> : <Mic size={16} />}
                {listening ? "Listening..." : "Speak task"}
              </button>
              {!speechSupported && (
                <p className="mt-2 text-xs text-moei-muted">
                  Voice input works best in Chrome or Edge. You can still type the same request above.
                </p>
              )}
              {activeFieldKey && (
                <p className="mt-2 text-xs font-medium text-moei-bronze">
                  Waiting for: {plan?.required_fields.find((field) => field.key === activeFieldKey)?.label}
                </p>
              )}
              {conversation.length > 0 && (
                <div className="mt-4 max-h-48 space-y-2 overflow-y-auto rounded-xl border border-moei-line bg-moei-cream/30 p-3">
                  {conversation.slice(-8).map((turn, index) => (
                    <div
                      key={`${turn.role}-${index}-${turn.text}`}
                      className={
                        "rounded-xl px-3 py-2 text-xs " +
                        (turn.role === "user"
                          ? "ml-auto max-w-[85%] bg-moei-ink text-white"
                          : "mr-auto max-w-[85%] border border-moei-line bg-white text-moei-body")
                      }
                    >
                      {turn.text}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {(message || plan || busy) && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                    {opening || busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-bold text-emerald-800">
                      {plan ? plan.title : "Automation status"}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-emerald-900/80">{message}</p>
                    {plan && (
                      <>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                            {plan.service}
                          </span>
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                            {plan.service_id}
                          </span>
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                            {Math.round(plan.confidence * 100)}% confidence
                          </span>
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                            {plan.action.replace(/_/g, " ")}
                          </span>
                        </div>
                        {plan.steps.length > 0 && (
                          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs leading-relaxed text-emerald-900/80">
                            {plan.steps.slice(0, 5).map((step) => <li key={step}>{step}</li>)}
                          </ol>
                        )}
                        {plan.required_documents.length > 0 && (
                          <div className="mt-3 text-xs text-emerald-900/80">
                            <span className="font-semibold">Documents: </span>
                            {plan.required_documents.join(", ")}
                          </div>
                        )}
                        {!plan.case_number && plan.required_fields.length > 0 && (
                          <div className="mt-4 rounded-xl border border-emerald-200 bg-white/70 p-3">
                            <div className="text-xs font-bold uppercase tracking-wider text-emerald-800">
                              Required customer details
                            </div>
                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              {plan.required_fields.map((field) => (
                                <label key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                                  <span className="text-xs font-semibold text-emerald-900">
                                    {field.label}
                                    {field.required ? " *" : ""}
                                  </span>
                                  {field.type === "textarea" ? (
                                    <textarea
                                      value={details[field.key] || ""}
                                      onChange={(e) => setDetails((d) => ({ ...d, [field.key]: e.target.value }))}
                                      placeholder={field.placeholder}
                                      rows={3}
                                      className="mt-1 w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-600"
                                    />
                                  ) : (
                                    <input
                                      value={details[field.key] || ""}
                                      onChange={(e) => setDetails((d) => ({ ...d, [field.key]: e.target.value }))}
                                      type={field.type}
                                      placeholder={field.placeholder}
                                      className="mt-1 w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-600"
                                    />
                                  )}
                                </label>
                              ))}
                            </div>
                            <button
                              onClick={() => submitPreparedRequest()}
                              disabled={submitting}
                              className="mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60"
                            >
                              {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                              Prepare request
                            </button>
                          </div>
                        )}
                        {plan.missing_information.length > 0 && (
                          <div className="mt-3 text-xs text-emerald-900/80">
                            <span className="font-semibold">Needed: </span>
                            {plan.missing_information.join(", ")}
                          </div>
                        )}
                        {plan.case_number && (
                          <div className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-xs font-semibold text-emerald-800">
                            Created case: {plan.case_number}
                          </div>
                        )}
                        {(plan.route || plan.external_url) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {plan.route && (
                              <button
                                onClick={() => router.push(plan.route!)}
                                className="inline-flex items-center gap-2 rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
                              >
                                Open workflow <ArrowRight size={14} />
                              </button>
                            )}
                            {plan.external_url && (
                              <a
                                href={plan.external_url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-2 rounded-full border border-emerald-700 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-50"
                              >
                                Official service page <ArrowRight size={14} />
                              </a>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="moei-card p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-moei-cream">
                <Home className="text-moei-bronze" size={20} />
              </div>
              <div>
                <div className="text-sm font-semibold text-moei-ink">LLM-backed planner</div>
                <div className="text-xs text-moei-muted">MOEI catalog + workflow tools</div>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {AUTOMATION_EXAMPLES.map((example) => (
                <button
                  key={example}
                  onClick={() => handleRequest(example, "text")}
                  disabled={opening || busy}
                  dir={isArabicText(example) ? "rtl" : "ltr"}
                  className="w-full rounded-xl border border-moei-line bg-white px-3 py-2 text-left text-sm text-moei-body transition hover:border-moei-bronze hover:text-moei-bronze disabled:opacity-60"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-moei-bronze/40 bg-white p-5 text-sm text-moei-body">
            <div className="font-semibold text-moei-ink">What it can complete</div>
            <ul className="mt-3 space-y-2 text-xs leading-relaxed text-moei-muted">
              <li>Understands service requests in Arabic or English using an LLM.</li>
                        <li>Chooses the best MOEI catalog service and action.</li>
                        <li>Opens implemented workflows, starting with housing loan rescheduling.</li>
              <li>Asks for required customer details before preparing other requests.</li>
              <li>Creates a CRM case and links the official service page.</li>
              <li>Leaves final declarations, uploads, and signatures for user confirmation.</li>
            </ul>
            <Link
              href="/chat"
              className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-moei-bronze hover:underline"
            >
              Ask a normal question in chat <ArrowRight size={13} />
            </Link>
          </div>
        </aside>
      </section>
    </div>
  );
}
