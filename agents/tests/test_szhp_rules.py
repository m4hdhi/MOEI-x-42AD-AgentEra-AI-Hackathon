"""Tests for the deterministic rules engine. Defends the 'tools-not-LLMs' claim."""

import pytest

from hassan.tools.szhp_rules import SzhpCase, szhp_rules_engine


def _case(**overrides):
    base = dict(
        emirates_id="784-1990-0000001-0",
        months_in_arrears=4,
        monthly_income_aed=12_000,
        monthly_installment_aed=3_500,
        outstanding_balance_aed=240_000,
        age=36,
        employment_status="employed",
        dependents=0,
        has_prior_reschedule=False,
    )
    base.update(overrides)
    return SzhpCase(**base)


def test_hardship_pathway_triggers_at_3_months():
    d = szhp_rules_engine(_case(months_in_arrears=3))
    assert any(r.rule_id == "SZHP-R3.1" for r in d.rule_hits)


def test_unemployed_forces_manual_review():
    d = szhp_rules_engine(_case(employment_status="unemployed", monthly_income_aed=2_000))
    assert d.recommendation == "manual_review"


def test_high_dti_forces_manual_review():
    # 600k balance / 36mo = 16.6k, way above 45% of 8k income → no affordable plan
    d = szhp_rules_engine(_case(monthly_income_aed=8_000, outstanding_balance_aed=600_000, months_in_arrears=5))
    assert d.recommendation == "manual_review"


def test_normal_employed_case_gets_approved():
    # Reasonable case: 20k income, 150k balance, employed → 12mo plan should fit
    d = szhp_rules_engine(_case(
        monthly_income_aed=20_000,
        outstanding_balance_aed=150_000,
        months_in_arrears=4,
        employment_status="employed",
    ))
    assert d.recommendation in ("approve", "approve_with_conditions")
    assert d.proposed_plan_months is not None
    assert d.new_monthly_installment_aed is not None
    assert any(p.affordable for p in d.plan_options)


def test_returns_multiple_plan_options():
    d = szhp_rules_engine(_case(monthly_income_aed=20_000, outstanding_balance_aed=240_000))
    assert len(d.plan_options) >= 3
    # Longer plans should have lower monthly payments
    monthlies = [p.monthly_aed for p in d.plan_options]
    assert monthlies == sorted(monthlies, reverse=True)


def test_summary_strings_present():
    d = szhp_rules_engine(_case())
    assert d.summary_en
    assert d.summary_ar
    assert "درهم" in d.summary_ar or "manual" in d.summary_en.lower()


def test_rule_citations_returned():
    d = szhp_rules_engine(_case())
    ids = {r.rule_id for r in d.rule_hits}
    # We always cite at least 3 rules so the audit trail always has a story.
    assert len(ids) >= 3
