#!/usr/bin/env python3
"""Create the Agent42 hackathon submission deck and form copy.

This intentionally uses only Python's standard library so it works even when
PowerPoint/LibreOffice/python-pptx are unavailable on the machine.
"""

from __future__ import annotations

import html
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
PPTX = OUT / "Agent42_MOEI_Omnichannel_AI_Pitch_Deck.pptx"
ANSWERS = OUT / "Agent42_Submission_Answers.md"

EMU = 914400
W = int(13.333333 * EMU)
H = int(7.5 * EMU)

INK = "102334"
DEEP = "071923"
BRONZE = "9C8853"
GOLD = "C6A664"
CREAM = "F7F1E6"
SAND = "E8DCC7"
GREEN = "007A53"
RED = "D8343A"
WHITE = "FFFFFF"
MUTED = "5E6A73"
PALE = "EEF7F2"
BLUE = "DCECF5"


def emu(v: float) -> int:
    return int(v * EMU)


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def shape_id_gen():
    i = 10
    while True:
        yield i
        i += 1


def tx_box(ids, text, x, y, w, h, size=24, color=INK, bold=False, align="l", fill=None):
    sid = next(ids)
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
        if fill
        else "<a:noFill/>"
    )
    paras = []
    for line in str(text).split("\n"):
        paras.append(
            f"""
            <a:p>
              <a:pPr algn="{align}"/>
              <a:r>
                <a:rPr lang="en-US" sz="{int(size * 100)}" dirty="0"{' b="1"' if bold else ''}>
                  <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
                  <a:latin typeface="Aptos"/>
                  <a:ea typeface="Aptos"/>
                  <a:cs typeface="Arial"/>
                </a:rPr>
                <a:t>{esc(line)}</a:t>
              </a:r>
            </a:p>
            """
        )
    return f"""
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{sid}" name="Text {sid}"/>
        <p:cNvSpPr txBox="1"/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        {fill_xml}
        <a:ln><a:noFill/></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720"/>
        <a:lstStyle/>
        {''.join(paras)}
      </p:txBody>
    </p:sp>
    """


def rect(ids, x, y, w, h, fill, line=None, radius=False):
    sid = next(ids)
    geom = "roundRect" if radius else "rect"
    ln = (
        f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        if line
        else '<a:ln><a:noFill/></a:ln>'
    )
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="{sid}" name="Shape {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
        <a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>
        {ln}
      </p:spPr>
    </p:sp>
    """


def line(ids, x1, y1, x2, y2, color=BRONZE, width=2):
    sid = next(ids)
    return f"""
    <p:cxnSp>
      <p:nvCxnSpPr><p:cNvPr id="{sid}" name="Line {sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x1)}" y="{emu(y1)}"/><a:ext cx="{emu(x2-x1)}" cy="{emu(y2-y1)}"/></a:xfrm>
        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
        <a:ln w="{int(width * 12700)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>
      </p:spPr>
    </p:cxnSp>
    """


def pic(ids, rid, x, y, w, h, name):
    sid = next(ids)
    return f"""
    <p:pic>
      <p:nvPicPr><p:cNvPr id="{sid}" name="{esc(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
      </p:spPr>
    </p:pic>
    """


def slide_xml(content: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {content}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def rels_xml(image_rels: list[tuple[str, str]]) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    ]
    for rid, target in image_rels:
        rels.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{target}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {''.join(rels)}
</Relationships>"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Agent42">
  <a:themeElements>
    <a:clrScheme name="Agent42">
      <a:dk1><a:srgbClr val="102334"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="071923"/></a:dk2><a:lt2><a:srgbClr val="F7F1E6"/></a:lt2>
      <a:accent1><a:srgbClr val="9C8853"/></a:accent1><a:accent2><a:srgbClr val="007A53"/></a:accent2>
      <a:accent3><a:srgbClr val="D8343A"/></a:accent3><a:accent4><a:srgbClr val="DCECF5"/></a:accent4>
      <a:accent5><a:srgbClr val="C6A664"/></a:accent5><a:accent6><a:srgbClr val="5E6A73"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Agent42"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Agent42"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def base_files(slide_count: int) -> dict[str, str]:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    presentation_rels = "\n".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    slide_ids = "\n".join(
        f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1)
    )
    return {
        "[Content_Types].xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="svg" ContentType="image/svg+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  {slide_overrides}
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
        "ppt/presentation.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{slide_count+1}"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{W}" cy="{H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>""",
        "ppt/_rels/presentation.xml.rels": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {presentation_rels}
  <Relationship Id="rId{slide_count+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId{slide_count+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>""",
        "ppt/theme/theme1.xml": theme_xml(),
        "ppt/slideMasters/slideMaster1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
</p:sldMaster>""",
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>""",
        "ppt/slideLayouts/slideLayout1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>""",
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>""",
    }


def footer(ids, i):
    return (
        tx_box(ids, "Agent42 | MOEI x 42 Abu Dhabi Hackathon", 0.45, 7.08, 7.5, 0.25, 8.5, MUTED)
        + tx_box(ids, f"{i}/7", 12.15, 7.08, 0.7, 0.25, 8.5, MUTED, align="r")
    )


def build_slides():
    slides: list[tuple[str, list[tuple[str, str]]]] = []

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, DEEP)
    c += rect(ids, 0, 0, 0.24, 7.5, RED)
    c += rect(ids, 0.24, 7.36, 13.09, 0.14, GREEN)
    c += tx_box(ids, "Agent42", 0.65, 0.72, 6.8, 1.1, 54, WHITE, True)
    c += tx_box(ids, "One AI agent for every MOEI customer channel", 0.72, 1.85, 7.2, 0.6, 24, GOLD, True)
    c += tx_box(ids, "WhatsApp • Voice • Web • Mobile • Sign Language • Task Automation", 0.75, 2.55, 8.0, 0.55, 15, "C7D6DD")
    c += tx_box(ids, "Team Agent42\nAli Saeed • Mahdhi Muzammil • Hasan Saleh", 0.75, 5.65, 8.0, 0.8, 18, WHITE, True)
    c += pic(ids, "rId2", 8.25, 0.78, 4.55, 2.6, "Sustainable service image")
    c += pic(ids, "rId3", 8.25, 3.67, 4.55, 2.65, "EV clean energy image")
    c += footer(ids, 1)
    slides.append((slide_xml(c), [("rId2", "smart-sustainable-building.svg"), ("rId3", "ev-clean-energy.svg")]))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, WHITE)
    c += tx_box(ids, "The problem: citizens repeat themselves across every channel", 0.55, 0.35, 10.6, 0.6, 30, INK, True)
    c += tx_box(ids, "MOEI customer engagement currently spans WhatsApp, contact center, website and mobile app, but context is fragmented.", 0.6, 1.05, 11.6, 0.55, 15, MUTED)
    labels = [
        ("Repeated effort", "Customer explains the same issue again on each channel."),
        ("Reactive service", "Follow-up happens after frustration, not before."),
        ("Limited visibility", "Leadership cannot see live omnichannel risk in one place."),
    ]
    for idx, (h, b) in enumerate(labels):
        x = 0.7 + idx * 4.1
        c += rect(ids, x, 2.0, 3.55, 2.05, "FFF7EF", BRONZE, True)
        c += tx_box(ids, h, x + 0.18, 2.22, 3.1, 0.45, 20, RED, True)
        c += tx_box(ids, b, x + 0.18, 2.84, 3.1, 0.75, 14, INK)
    c += rect(ids, 1.0, 4.9, 11.2, 1.05, INK, None, True)
    c += tx_box(ids, "Our claim: one persistent AI service layer can cut effort, speed resolution, and give MOEI live operational control.", 1.25, 5.11, 10.7, 0.55, 20, WHITE, True, "ctr")
    c += footer(ids, 2)
    slides.append((slide_xml(c), []))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, CREAM)
    c += tx_box(ids, "What we built: a working omnichannel agent system", 0.55, 0.34, 11.2, 0.6, 30, INK, True)
    c += tx_box(ids, "Not just a chatbot. A connected service operating layer.", 0.6, 1.02, 8.0, 0.45, 15, MUTED)
    features = [
        ("Meta WhatsApp Cloud API", "Production webhook, signature check, wa.me QR entry."),
        ("Voice + Arabic handling", "Call page detects Arabic and replies in Arabic."),
        ("Web, mobile, sign", "Shared memory/history across citizen channels."),
        ("Task automation", "LLM planner routes service requests and opens workflows."),
        ("UAE PASS profiles", "Demo identities, account page, linked case history."),
        ("Document intelligence", "Salary certificate / Emirates ID detection and storage."),
    ]
    for idx, (h, b) in enumerate(features):
        x = 0.65 + (idx % 3) * 4.18
        y = 1.8 + (idx // 3) * 2.05
        c += rect(ids, x, y, 3.65, 1.45, WHITE, "E0D2B8", True)
        c += tx_box(ids, h, x + 0.2, y + 0.16, 3.25, 0.36, 16, GREEN, True)
        c += tx_box(ids, b, x + 0.2, y + 0.62, 3.2, 0.58, 11.8, INK)
    c += footer(ids, 3)
    slides.append((slide_xml(c), []))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, DEEP)
    c += tx_box(ids, "Architecture: one brain, specialist agents, live audit", 0.55, 0.35, 11.8, 0.6, 30, WHITE, True)
    for idx, ch in enumerate(["WhatsApp", "Voice", "Web Chat", "Mobile", "Sign"]):
        x = 0.55 + idx * 2.55
        c += rect(ids, x, 1.2, 2.1, 0.62, BRONZE, None, True)
        c += tx_box(ids, ch, x + 0.05, 1.32, 2.0, 0.26, 12.5, WHITE, True, "ctr")
        c += line(ids, x + 1.05, 1.85, 6.65, 2.72, GREEN, 1.3)
    c += rect(ids, 3.15, 2.72, 7.0, 0.85, WHITE, GOLD, True)
    c += tx_box(ids, "FastAPI Channel Gateway", 3.35, 2.93, 6.6, 0.3, 18, INK, True, "ctr")
    c += line(ids, 6.65, 3.58, 6.65, 4.05, GREEN, 2)
    c += rect(ids, 2.15, 4.05, 9.0, 0.95, RED, None, True)
    c += tx_box(ids, "LangGraph Supervisor: route → remember → guardrail → execute → escalate → reply", 2.32, 4.28, 8.65, 0.3, 16, WHITE, True, "ctr")
    workers = ["Housing Rules", "CRM Cases", "Knowledge/RAG", "Notifications", "Audit Trail"]
    for idx, w in enumerate(workers):
        x = 0.75 + idx * 2.52
        c += line(ids, 6.65, 5.0, x + 1.0, 5.52, GREEN, 1.2)
        c += rect(ids, x, 5.52, 2.0, 0.8, GREEN, None, True)
        c += tx_box(ids, w, x + 0.08, 5.72, 1.85, 0.24, 11.2, WHITE, True, "ctr")
    c += tx_box(ids, "Postgres system of record • Redis memory • Langfuse traces • Web-host deployment", 0.9, 6.55, 11.5, 0.32, 12, "C7D6DD", align="ctr")
    c += footer(ids, 4)
    slides.append((slide_xml(c), []))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, WHITE)
    c += tx_box(ids, "Live demo path in 5 minutes", 0.55, 0.35, 10.6, 0.6, 30, INK, True)
    steps = [
        ("1", "Ask in WhatsApp / chat", "Arabic or English question; shared memory starts."),
        ("2", "Automate a task", "Voice or chat request opens the right service workflow."),
        ("3", "Reschedule SZHP arrears", "Rules engine calculates safe housing plan."),
        ("4", "Upload documents", "Salary certificate and Emirates ID classified and saved."),
        ("5", "Admin sees reality", "Executive dashboard, co-pilot, audit trail update live."),
    ]
    for idx, (num, h, b) in enumerate(steps):
        y = 1.28 + idx * 1.05
        c += rect(ids, 0.8, y, 0.62, 0.62, RED if idx == 2 else BRONZE, None, True)
        c += tx_box(ids, num, 0.86, y + 0.12, 0.5, 0.24, 15, WHITE, True, "ctr")
        c += tx_box(ids, h, 1.65, y + 0.02, 3.6, 0.3, 17, INK, True)
        c += tx_box(ids, b, 1.65, y + 0.36, 5.35, 0.28, 11.5, MUTED)
    c += pic(ids, "rId2", 7.6, 1.2, 4.9, 2.7, "Housing handover")
    c += rect(ids, 7.6, 4.25, 4.9, 1.45, PALE, GREEN, True)
    c += tx_box(ids, "Demo URLs", 7.85, 4.42, 4.3, 0.28, 16, GREEN, True)
    c += tx_box(ids, "localhost:3000/chat\nlocalhost:3000/automation\nlocalhost:3000/admin/exec\nlocalhost:3000/admin/audit", 7.85, 4.78, 4.3, 0.72, 12, INK)
    c += footer(ids, 5)
    slides.append((slide_xml(c), [("rId2", "housing-handover.svg")]))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, CREAM)
    c += tx_box(ids, "Why it matters: measurable federal impact", 0.55, 0.35, 11.3, 0.6, 30, INK, True)
    metrics = [
        ("90 sec", "end-to-end guided service flow"),
        ("24/7", "Arabic + English support"),
        ("1 profile", "citizen context across channels"),
        ("0 repeat", "same issue does not restart"),
    ]
    for idx, (n, label) in enumerate(metrics):
        x = 0.7 + idx * 3.1
        c += rect(ids, x, 1.35, 2.62, 1.55, WHITE, "D9C9AA", True)
        c += tx_box(ids, n, x + 0.1, 1.55, 2.42, 0.52, 30, RED if idx == 0 else GREEN, True, "ctr")
        c += tx_box(ids, label, x + 0.2, 2.17, 2.22, 0.38, 12, INK, align="ctr")
    c += rect(ids, 0.8, 3.65, 5.6, 1.55, WHITE, BRONZE, True)
    c += tx_box(ids, "For citizens", 1.05, 3.85, 5.0, 0.32, 17, BRONZE, True)
    c += tx_box(ids, "Less effort, faster answers, accessible service, proactive updates.", 1.05, 4.28, 5.0, 0.38, 14, INK)
    c += rect(ids, 6.95, 3.65, 5.6, 1.55, WHITE, BRONZE, True)
    c += tx_box(ids, "For MOEI", 7.2, 3.85, 5.0, 0.32, 17, BRONZE, True)
    c += tx_box(ids, "Live KPIs, SLA risk, agent co-pilot, auditable AI decisions.", 7.2, 4.28, 5.0, 0.38, 14, INK)
    c += tx_box(ids, "Built for web-host deployment: no Docker required at runtime; managed Postgres/Redis supported.", 0.85, 6.1, 11.6, 0.4, 14, MUTED, align="ctr")
    c += footer(ids, 6)
    slides.append((slide_xml(c), []))

    ids = shape_id_gen()
    c = rect(ids, 0, 0, 13.33, 7.5, DEEP)
    c += tx_box(ids, "Agent42 is submission-ready", 0.55, 0.45, 10.8, 0.65, 34, WHITE, True)
    c += tx_box(ids, "Omnichannel AI Customer Engagement Agent", 0.6, 1.18, 8.5, 0.42, 18, GOLD, True)
    c += pic(ids, "rId2", 8.15, 0.65, 4.4, 2.5, "EV future")
    checklist = [
        "Working web, mobile, voice, sign and WhatsApp surfaces",
        "Housing arrears rescheduling workflow with SZHP rules",
        "Task automation agent for customer service requests",
        "Live executive dashboard, co-pilot, cases and audit trail",
        "Secure UAE PASS demo identities and document storage",
        "GitHub main branch cleaned and pushed",
    ]
    for idx, item in enumerate(checklist):
        y = 2.0 + idx * 0.62
        c += rect(ids, 0.8, y + 0.06, 0.26, 0.26, GREEN, None, True)
        c += tx_box(ids, item, 1.16, y - 0.02, 6.3, 0.34, 14, WHITE)
    c += rect(ids, 7.85, 3.62, 4.8, 1.25, "12364A", GOLD, True)
    c += tx_box(ids, "Ask", 8.1, 3.82, 4.3, 0.28, 15, GOLD, True)
    c += tx_box(ids, "Select Agent42 for the Omnichannel AI Customer Engagement Agent track.", 8.1, 4.16, 4.25, 0.42, 16, WHITE, True)
    c += tx_box(ids, "Thank you", 0.6, 6.25, 6.5, 0.5, 26, GOLD, True)
    c += footer(ids, 7)
    slides.append((slide_xml(c), [("rId2", "ev-clean-energy.svg")]))

    return slides


def write_pptx():
    OUT.mkdir(exist_ok=True)
    image_src = ROOT / "apps/web/public/news"
    slides = build_slides()
    files = base_files(len(slides))
    with zipfile.ZipFile(PPTX, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in files.items():
            z.writestr(path, content)
        copied = set()
        for i, (xml, image_rels) in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", xml)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rels_xml(image_rels))
            for _, img in image_rels:
                if img not in copied:
                    z.write(image_src / img, f"ppt/media/{img}")
                    copied.add(img)


def write_answers():
    repo = "https://github.com/m4hdhi/MOEI-x-42AD-AgentEra-AI-Hackathon"
    text = f"""# Agent42 Hackathon Submission Pack

## Form Fields

**Competition**  
Agentera - MOEI X 42 Abu Dhabi Hackathon

**Team**  
Agent42

**Team Members**  
Ali Saeed, Mahdhi Muzammil, Hasan Saleh

**Project Name**  
Agent42 - MOEI Omnichannel AI Customer Engagement Agent

**One-line Tagline**  
One AI agent that remembers every citizen across WhatsApp, voice, web, mobile, sign language, and service workflows.

**Track**  
Omnichannel AI Customer Engagement Agent

**Problem Statement**  
MOEI customers interact across WhatsApp, the contact center, website, and mobile services, but each channel often behaves like a separate journey. Citizens repeat the same issue, service teams lack a unified live view, and leadership cannot easily see cross-channel sentiment, SLA risk, escalation pressure, or service completion status. Housing arrears rescheduling is especially sensitive because customers need fast, accurate, policy-aware guidance with document checks and human escalation when required.

**Solution Description**  
Agent42 is a working omnichannel AI customer engagement layer for MOEI. It connects WhatsApp via Meta Cloud API, web chat, mobile, voice call, sign-language assisted chat, and task automation into one LangGraph supervisor with shared memory and a unified citizen profile. The system detects Arabic/English, routes requests to specialist service agents, creates CRM cases, stores and classifies customer documents such as Emirates ID and salary certificates, and guides Sheikh Zayed Housing loan arrears rescheduling using policy-aware rules.  

For staff and leadership, Agent42 includes live executive dashboards, customer co-pilot views, citizen account history, case follow-up, analytics, call recordings, and an auditable “Right to Explanation” trail showing real agent decisions or reconstructed CRM timelines. It is built for web-host deployment with managed Postgres/Redis support, while Docker remains optional for local infrastructure.

**Demo URL**  
Local demo: http://localhost:3000  
Public demo URL: add your hosted/Vercel URL here if deployed before submission.

**Demo Video URL**  
Add your uploaded demo video URL here.

**Pitch Deck URL**  
{repo}

**GitHub Repository URL**  
{repo}

## 5-Minute Pitch Run of Show

1. **0:00-0:35 - Hook:** A citizen should not repeat the same issue across every MOEI channel. Agent42 gives MOEI one service brain.
2. **0:35-1:10 - Problem:** WhatsApp, voice, web and mobile are fragmented. Staff and leadership need unified context, SLA visibility and proactive engagement.
3. **1:10-2:30 - Live demo:** Show chat/WhatsApp-style request, Arabic/English handling, task automation, and housing arrears rescheduling.
4. **2:30-3:35 - Trust layer:** Show document detection, UAE PASS identity, account history, CRM case creation and audit trail.
5. **3:35-4:30 - Staff layer:** Show admin exec dashboard, co-pilot, active citizens, cases and follow-up.
6. **4:30-5:00 - Close:** Agent42 is a deployable omnichannel operating layer for MOEI, not a single chatbot.

## Upload Files

- Pitch Deck File: `{PPTX.name}`
- Presentation Slides: `{PPTX.name}`
"""
    ANSWERS.write_text(text, encoding="utf-8")


def main():
    if OUT.exists():
        # Keep the folder clean for a submission upload pack.
        for item in OUT.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    OUT.mkdir(exist_ok=True)
    write_pptx()
    write_answers()
    print(PPTX)
    print(ANSWERS)


if __name__ == "__main__":
    main()
