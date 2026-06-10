#!/usr/bin/env bash
# Scripted end-to-end demo of the cross-channel Housing Maintenance journey for Agent42.
#
#   make smoke-demo                 # against http://localhost:8000
#   BASE_URL=https://x.ngrok BASE_URL=... bash scripts/smoke_demo.sh
#
# Walks one citizen (DEMO-001 — seed first with `uv run python scripts/seed_demo_citizen.py`)
# across web → WhatsApp → proactive push → agent handoff → mobile closure, asserting the
# unified profile and cross-channel memory hold the whole way through.
#
# Not `set -e`: every step prints PASS/FAIL and we still render the final scoreboard.
set -uo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
USER_ID="DEMO-001"

bold=$'\033[1m'; green=$'\033[32m'; red=$'\033[31m'; dim=$'\033[2m'; reset=$'\033[0m'
PASS_ALL=1

say()  { printf '\n%s━━ %s %s%s\n' "$bold" "$1" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" "$reset"; }
ok()   { printf '  %s✓ %s%s\n' "$green" "$1" "$reset"; }
bad()  { printf '  %s✗ %s%s\n' "$red" "$1" "$reset"; PASS_ALL=0; }
show() { printf '%s%s%s\n' "$dim" "$1" "$reset"; }

# Read a top-level string field from JSON on stdin.
jget() { python3 -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: d={}
v=d.get('$1','')
print(v if v is not None else '')"; }

chat() {  # chat <channel> <language> <session> <text>
  curl -s -X POST "$BASE/chat/web" -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys; print(json.dumps({'user_id':'$USER_ID','channel':sys.argv[1],'session_id':sys.argv[2],'language':sys.argv[3],'text':sys.argv[4]}))" "$1" "$3" "$2" "$4")"
}

# ── Pre-flight ──────────────────────────────────────────────────────────────────────────
if ! curl -s -m 3 "$BASE/healthz" >/dev/null; then
  printf '%s✗ API not reachable at %s — start it with `make api`.%s\n' "$red" "$BASE" "$reset"
  exit 1
fi

# ══ STEP 1 — Website intent ═══════════════════════════════════════════════════════════════
say "STEP 1 · Website intent (web, EN)"
show "Ahmed reports a housing maintenance issue on the website."
RESP=$(chat web en demo-web-1 "I have a crack in the ceiling of my MOEI housing unit")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
CASE_ID=$(printf '%s' "$RESP" | jget case_number)
if [ -n "$CASE_ID" ]; then ok "Case opened: $CASE_ID"; else bad "No case_id in response"; fi
sleep 2

# ══ STEP 2 — WhatsApp follow-up (Arabic) ══════════════════════════════════════════════════
say "STEP 2 · WhatsApp follow-up (whatsapp, AR)"
show "Same citizen, now on WhatsApp, asks in Arabic for an update — no re-identification."
RESP=$(chat whatsapp ar demo-wa-1 "ما هو آخر تحديث على طلبي؟")
REPLY=$(printf '%s' "$RESP" | jget text)
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
CROSS_CHANNEL="NO"
if [ -n "$CASE_ID" ] && printf '%s' "$REPLY" | grep -qF "$CASE_ID"; then
  ok "WhatsApp reply references $CASE_ID — unified profile, no re-identification"
  CROSS_CHANNEL="YES"
else
  bad "WhatsApp reply did not reference $CASE_ID"
fi
sleep 2

# ══ STEP 3 — Proactive notification ═══════════════════════════════════════════════════════
say "STEP 3 · Proactive update (agent reaches out first)"
show "MOEI pushes a status update to Ahmed's preferred channel."
CODE=$(curl -s -o /tmp/agent42_trigger.json -w '%{http_code}' \
  -X POST "$BASE/cases/$CASE_ID/trigger-update" -H 'Content-Type: application/json' \
  -d '{"message":"Your maintenance request has been assigned — field visit scheduled for Thursday"}')
python3 -m json.tool < /tmp/agent42_trigger.json 2>/dev/null || cat /tmp/agent42_trigger.json
if [ "$CODE" = "200" ]; then ok "Proactive update sent (HTTP 200)"; else bad "trigger-update returned HTTP $CODE"; fi
sleep 2

# ══ STEP 4 — Agent handoff context card ═══════════════════════════════════════════════════
say "STEP 4 · Agent handoff context card"
show "A human agent opens the case — one screen, full context, zero repetition."
RESP=$(curl -s "$BASE/crm/agent-context?case_id=$CASE_ID")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
printf '%s' "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
need = ['customer_name','case_summary','sentiment','recommended_action','interaction_history']
missing = [k for k in need if k not in d or d[k] in (None,'')]
hist = d.get('interaction_history') or []
fails = []
if missing: fails.append('missing fields: ' + ', '.join(missing))
if len(hist) < 2: fails.append(f'interaction_history has {len(hist)} entries (<2)')
if fails:
    print('FAIL:: ' + ' ; '.join(fails)); sys.exit(1)
print(f'OK:: {d[\"customer_name\"]} · sentiment={d[\"sentiment_label\"]} · {len(hist)} interactions across {d.get(\"channels_seen\")}')
" > /tmp/agent42_ctx.txt 2>&1
if grep -q '^OK::' /tmp/agent42_ctx.txt; then ok "Context card complete — $(sed 's/^OK:: //' /tmp/agent42_ctx.txt)"
else bad "Context card incomplete — $(sed 's/^FAIL:: //' /tmp/agent42_ctx.txt)"; fi
sleep 2

# ══ STEP 5 — Mobile app closure ═══════════════════════════════════════════════════════════
say "STEP 5 · Mobile closure (mobile)"
show "Ahmed confirms on the mobile app that the technician fixed it."
RESP=$(chat mobile en demo-mob-1 "The technician came and fixed it, thank you")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
sleep 2
CASE_JSON=$(curl -s "$BASE/crm/cases/$CASE_ID")
STATUS=$(printf '%s' "$CASE_JSON" | jget status)
RESOLUTION=$(printf '%s' "$CASE_JSON" | jget resolution_type)
AUTO_RESOLVED="NO"
if [ "$STATUS" = "resolved" ] && [ -n "$RESOLUTION" ] && [ "$RESOLUTION" != "pending" ]; then
  ok "Case auto-resolved: status=$STATUS · resolution_type=$RESOLUTION"
  AUTO_RESOLVED="YES"
else
  bad "Case not resolved (status=$STATUS · resolution_type=${RESOLUTION:-none})"
fi

# ══ Summary ═══════════════════════════════════════════════════════════════════════════════
say "DEMO COMPLETE"
printf '  Case: %s\n' "$CASE_ID"
printf '  Cross-channel context preserved: %s\n' "$CROSS_CHANNEL"
printf '  Case auto-resolved: %s\n' "$AUTO_RESOLVED"
[ "$PASS_ALL" = "1" ] && printf '%s  ALL STEPS PASSED%s\n' "$green" "$reset" \
  || printf '%s  SOME STEPS FAILED (see ✗ above)%s\n' "$red" "$reset"
exit $(( PASS_ALL == 1 ? 0 : 1 ))
