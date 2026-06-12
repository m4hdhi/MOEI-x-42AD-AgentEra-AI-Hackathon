"""Generate the Agent42 5-minute demo speaker-notes PDF (reMarkable-friendly, A4 portrait).

Two tracks: ALI (presenter, speaks) and MAHDHI (drives the laptop / demo steps).
  uv run python scripts/make_speaker_notes.py
"""

from pathlib import Path
from fpdf import FPDF

INK = (24, 28, 36)
GRAY = (90, 96, 105)
BRONZE = (156, 136, 83)
SAY_BG = (244, 245, 247)
DO_BG = (228, 231, 236)
LINE = (210, 214, 220)


class Notes(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(8)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 5, "Agent42  -  5-Minute Demo Speaker Notes", align="L")
        self.cell(0, 5, f"p.{self.page_no()}", align="R")
        self.ln(7)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRAY)
        self.cell(0, 5, "Ali = presenter (speak)    |    Mahdhi = laptop / demo steps", align="C")


def act(pdf, time, title):
    pdf.ln(2)
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_fill_color(*INK)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.cell(28, 9, f" {time}", fill=True)
    pdf.cell(0, 9, f"  {title}", fill=True, ln=1)
    pdf.ln(2)


def say(pdf, text):
    _block(pdf, "ALI  -  SAY", text, SAY_BG, INK, BRONZE, body_style="")


def emph(pdf, text):
    _block(pdf, "ALI  -  SAY  (with energy)", text, SAY_BG, INK, BRONZE, body_style="I")


def do(pdf, text):
    _block(pdf, "MAHDHI  -  DO", text, DO_BG, INK, INK, body_style="B")


def _block(pdf, label, text, bg, label_color, bar_color, body_style):
    # page-break guard
    if pdf.get_y() > 255:
        pdf.add_page()
    x0 = pdf.l_margin
    w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_x(x0 + 3)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*label_color)
    pdf.cell(0, 5, label, ln=1)
    # body in a filled box with a left bar
    pdf.set_font("Helvetica", body_style, 11.5)
    pdf.set_text_color(*INK)
    y_start = pdf.get_y()
    pdf.set_fill_color(*bg)
    pdf.set_x(x0 + 3)
    pdf.multi_cell(w - 3, 6.2, text, fill=True)
    y_end = pdf.get_y()
    # left accent bar
    pdf.set_fill_color(*bar_color)
    pdf.rect(x0, y_start, 2.2, y_end - y_start, style="F")
    pdf.ln(2.5)


def bullets(pdf, items, color=INK):
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(*color)
    for it in items:
        pdf.set_x(pdf.l_margin + 2)
        pdf.multi_cell(0, 5.6, f"-  {it}")
    pdf.ln(1)


def build():
    pdf = Notes(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_margins(16, 14, 16)
    pdf.add_page()

    # ---- Title ----
    pdf.set_text_color(*BRONZE)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "MINISTRY OF ENERGY & INFRASTRUCTURE", ln=1)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 26)
    pdf.cell(0, 13, "Agent42", ln=1)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 8, "5-Minute Demo  -  Speaker Notes", ln=1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*INK)
    pdf.ln(1)
    pdf.cell(0, 6, "Presenter (speak): ALI        Laptop / demo steps: MAHDHI", ln=1)
    pdf.ln(3)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    # ---- Setup ----
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, "Before you start (2 minutes) - MAHDHI", ln=1)
    bullets(pdf, [
        "Open 5 tabs, already signed in (no logins on stage):",
        "   1) Chat            localhost:3000/chat",
        "   2) Mobile          localhost:3000/mobile",
        "   3) Rescheduling    localhost:3000/rescheduling",
        "   4) Officer console localhost:3000/admin/rescheduling",
        "   5) Intelligence    localhost:3000/admin/intelligence",
        "Citizen login: Mariam Al Mansouri  ->  784-1990-1181000-4  (cross-channel history + hardship loan).",
        "Admin password: admin     |     API running with --env-file .env  (briefings = live AI).",
        "Pre-type the chat message and the briefing input. On stage you ONLY press Enter / click.",
    ])
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Timing (keep to 5:00)", ln=1)
    bullets(pdf, [
        "Problem 0:50   |   Cross-channel 1:10   |   Officer 1:30   |   Leadership 0:45   |   Close 0:45",
    ])

    # ---- ACT 0 ----
    act(pdf, "0:00-0:50", "ACT 0  -  The Problem   (slide only, no screen)")
    say(pdf, "Meet Mariam - a UAE citizen. Recently she hit a hard moment: she needs the Ministry's "
             "support to keep benefiting from her housing service.")
    say(pdf, "Today, her only option is to reach out - so she calls the contact centre. She waits. She "
             "spends over FORTY MINUTES explaining her whole situation. The call ends with no decision - "
             "just 'we'll get back to you.'")
    say(pdf, "Days pass. No update. So she tries again, this time on WhatsApp - and has to explain "
             "everything from scratch. Different channel, zero memory, same frustration. That is how a "
             "citizen's trust turns into anxiety.")
    say(pdf, "The problem isn't the service. It's the FRAGMENTATION - every channel forgets her, and "
             "every decision waits for a human. This is where Agent42 comes in.")
    emph(pdf, "Agent42 is one intelligent layer for the Ministry: it remembers Mariam everywhere, it "
              "decides like an officer in seconds, and it even advises leadership. Let me show you.")
    do(pdf, "Stay on the title / problem slide. Have the CHAT tab ready to bring up.")

    # ---- ACT 1 ----
    act(pdf, "0:50-2:00", "ACT 1  -  One brain, every channel")
    do(pdf, "Switch to the CHAT tab (already signed in as Mariam).")
    say(pdf, "Mariam opens the assistant and simply asks about her request.")
    do(pdf, "In Chat, send the pre-typed message:  \"What's the status of my request?\"  (press Enter)")
    say(pdf, "Notice - she never introduced herself. Agent42 already knows her from her verified identity, "
             "pulls her UNIFIED PROFILE, and answers with her real case, the exact status, and the SLA - "
             "then closes it autonomously. No agent, no hold music.")
    do(pdf, "Switch to the MOBILE tab.")
    say(pdf, "She moves to the mobile app - and the conversation is ALREADY THERE, continuing across "
             "channels. She never repeats herself again. One identity, one memory, every channel.")

    # ---- ACT 2 ----
    act(pdf, "2:00-3:30", "ACT 2  -  An autonomous officer, in seconds")
    say(pdf, "Now her real need: she's fallen behind on her housing loan and needs it rescheduled. Today "
             "that is a FIVE-DAY manual review. Watch Agent42 do the officer's job.")
    do(pdf, "Switch to the RESCHEDULING tab  (/rescheduling).")
    say(pdf, "It retrieves her loan and arrears AUTOMATICALLY - no forms. She uploads her salary "
             "certificate, confirms it's authentic, and submits.")
    do(pdf, "Click 'Upload certificate' (pick any file)  ->  tick the authenticity box  ->  click Submit.")
    say(pdf, "In SECONDS - a decision. Because her income is strained, Agent42 does NOT raise her "
             "instalment - it moves the arrears to the END of her loan, keeping her within the 20% "
             "deduction rule and the original loan period. And it explains exactly why.")
    do(pdf, "Switch to the OFFICER tab  (/admin/rescheduling).")
    say(pdf, "And it's GOVERNED. Every decision lands in the officer's console - here, 86% auto-decided, "
             "with confidence scores, policy-compliance checks, and a full audit trail. Humans handle only "
             "the exceptions. Five days becomes seconds - fairly, transparently, consistently.")

    # ---- ACT 3 ----
    act(pdf, "3:30-4:15", "ACT 3  -  A strategic advisor for leadership")
    say(pdf, "Agent42 doesn't stop at citizens - it serves LEADERSHIP too. Imagine a minister has a "
             "meeting with Germany on green hydrogen in fifteen minutes.")
    do(pdf, "Switch to the INTELLIGENCE tab (/admin/intelligence)  ->  pick Germany  ->  'Prepare me for "
            "a meeting' tab  ->  input already says 'green hydrogen offtake'  ->  click Generate briefing.")
    say(pdf, "Instantly - an EXECUTIVE BRIEFING: talking points, opportunities, risks, recommended "
             "actions, even smart questions to ask - grounded in trusted data, in Arabic or English. "
             "Meeting-ready in seconds instead of days of preparation.")

    # ---- ACT 4 ----
    act(pdf, "4:15-5:00", "ACT 4  -  Impact & Close")
    do(pdf, "Switch to the closing slide (or the Executive Dashboard).")
    say(pdf, "So what did Mariam's day become?")
    bullets(pdf, [
        "40 minutes of repeating  ->  ZERO. One identity, remembered across every channel.",
        "A 5-day wait  ->  an instant, explainable, GOVERNED decision.",
        "The same intelligence that served Mariam also prepares the Ministry's leaders for the world stage.",
    ])
    say(pdf, "Every interaction is logged for full transparency and the right to explanation. And it's "
             "bilingual and accessible by design - including for people of determination.")
    emph(pdf, "Agent42 isn't a chatbot. It's the Ministry's intelligence layer - turning fragmented, slow, "
              "manual service into one experience that is INSTANT, FAIR, and HUMAN. Thank you.")

    # ---- Recovery tips ----
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*BRONZE)
    pdf.cell(0, 7, "If something stalls (both of you)", ln=1)
    bullets(pdf, [
        "Ali: narrate over it - '...and while that resolves...' - never go silent.",
        "Mahdhi: keep every tab pre-loaded; don't navigate fresh on stage; only press Enter on pre-typed inputs.",
        "If a tab errors: hard-refresh once (Cmd+Shift+R) and continue; have a backup screenshot ready.",
    ], color=GRAY)

    out = Path.home() / "Downloads" / "Agent42_Demo_SpeakerNotes.pdf"
    pdf.output(str(out))
    # also drop a copy in the repo
    repo = Path(__file__).resolve().parents[1] / "docs" / "Agent42_Demo_SpeakerNotes.pdf"
    repo.parent.mkdir(exist_ok=True)
    pdf.output(str(repo))
    print("Wrote:", out)
    print("Wrote:", repo)


if __name__ == "__main__":
    build()
