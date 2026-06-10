"""HousingAgent end-to-end test — pure function, no LLM/network."""

import pytest

from hassan.workers.housing import run_housing_agent


@pytest.mark.asyncio
async def test_housing_asks_for_missing_income_and_balance():
    """When critical info missing, worker should ask — not guess."""
    result = await run_housing_agent(
        text="I'm 4 months behind on my SZHP loan",
        user_id="784-1990-1181000-4",
        language="en",
    )
    assert result.decision is None
    assert "monthly_income_aed" in result.needs_more_info
    assert "outstanding_balance_aed" in result.needs_more_info
    assert "income" in result.draft_en.lower() or "salary" in result.draft_en.lower()


@pytest.mark.asyncio
async def test_housing_recommends_when_facts_present():
    result = await run_housing_agent(
        text="I'm 4 months behind on my SZHP loan, my salary is 20000 AED and the outstanding balance is 150000",
        user_id="784-1990-1181000-4",
        language="en",
    )
    assert result.decision is not None
    assert result.draft_en
    assert "Risk band" in result.draft_en
    # Should find an affordable plan and not always escalate
    assert result.decision.recommendation in ("approve", "approve_with_conditions")
    assert any(tc["tool"] == "szhp_rules_engine" for tc in result.tool_calls)


@pytest.mark.asyncio
async def test_housing_extracts_facts_from_memory():
    """Facts stated in a previous turn should carry forward."""
    memory = [
        "[web] user: I'm 4 months behind on my SZHP loan",
        "[web] assistant: To check eligibility I need your salary and outstanding balance.",
        "[web] user: my salary is 20000 AED",
    ]
    result = await run_housing_agent(
        text="and my outstanding balance is 150000",
        user_id="784-1990-1181000-4",
        language="en",
        memory_snippets=memory,
    )
    assert result.decision is not None, f"Should have full case from memory, got: {result.draft_en}"
    assert result.decision.recommendation in ("approve", "approve_with_conditions")


@pytest.mark.asyncio
async def test_housing_rejects_unknown_emirates_id():
    result = await run_housing_agent(
        text="help me reschedule",
        user_id="000-0000-0000000-0",
        language="en",
    )
    assert result.decision is None
    assert "Emirates ID" in result.draft_en or "هوية" in result.draft_ar


@pytest.mark.asyncio
async def test_housing_arabic_draft_when_facts_present():
    result = await run_housing_agent(
        text="أحتاج تأجيل قسط السكن، راتبي 20000 درهم والرصيد المتبقي 150000",
        user_id="784-1990-1181000-4",
        language="ar",
    )
    assert result.draft_ar
    arabic_markers = ["درهم", "إعادة", "مراجعة", "مخاطر", "قضية", "قسط", "جدولة"]
    assert any(m in result.draft_ar for m in arabic_markers), result.draft_ar
