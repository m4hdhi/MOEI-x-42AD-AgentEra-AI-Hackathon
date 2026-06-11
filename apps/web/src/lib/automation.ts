import { API_URL } from "@/lib/utils";

export type TaskMode = "voice" | "text";

export type AutomationPlan = {
  ok: boolean;
  language: "ar" | "en";
  intent: string;
  service_id: string;
  service: string;
  title: string;
  confidence: number;
  action: "open_workflow" | "create_case" | "ask_clarifying_question" | "answer";
  reason: string;
  reply: string;
  missing_information: string[];
  steps: string[];
  executable: boolean;
  route?: string | null;
  external_url?: string | null;
  case_number?: string | null;
  required_documents: string[];
  required_fields: {
    key: string;
    label: string;
    type: "text" | "textarea" | "tel" | "email" | "number";
    required: boolean;
    placeholder: string;
  }[];
  workflow_name?: string | null;
};

export const AUTOMATION_EXAMPLES = [
  "I want to request loan rescheduling for my Sheikh Zayed Housing loan",
  "Renew my pleasure boat registration",
  "Apply for a national transportation vehicle permit",
  "File a complaint about my housing assistance request",
  "أريد إعادة جدولة قرض برنامج الشيخ زايد للإسكان",
];

export function isArabicText(text: string) {
  return /[\u0600-\u06ff\u0750-\u077f]/.test(text);
}

export function looksLikeAutomationRequest(text: string) {
  const t = text.toLowerCase();
  return (
    /\b(apply|request|renew|register|submit|file|create|open|start|automate|do it|complete|fill)\b/.test(t) ||
    /(أريد|اريد|قدم|تقديم|جدد|تجديد|سجل|تسجيل|افتح|ابدأ|ابدا|أنشئ|انشئ|شكوى|طلب)/.test(text)
  );
}

export async function requestAutomationPlan(
  text: string,
  mode: TaskMode,
  options?: { execute?: boolean; details?: Record<string, string> },
): Promise<AutomationPlan> {
  const res = await fetch(`${API_URL}/automation/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      text,
      channel: mode === "voice" ? "voice" : "web",
      language: "auto",
      execute: options?.execute ?? false,
      details: options?.details ?? {},
    }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Automation Agent failed (${res.status})`);
  }
  return res.json();
}
