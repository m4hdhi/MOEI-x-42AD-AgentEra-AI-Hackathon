"""Sheikh Zayed Housing Programme — Loan Arrears Rescheduling decision engine.

DETERMINISTIC officer-grade assessment. The agent never invents policy: it applies the
Programme's published rules and the rescheduling assessment matrix in pure Python, so every
recommendation is explainable, consistent, and auditable.

Core rules (from the Programme guide):
  Rule 1 — Monthly deduction must not exceed 20% of the beneficiary's income.
  Rule 2 — The proposed repayment period must not exceed the original approved period.
  Rule 3 — An existing active rescheduling request → automatic rejection.

Assessment matrix → recommended path:
  • UPDATE_INSTALLMENT — raise the instalment to clear arrears over N months, staying ≤20%.
  • TRANSFER_ARREARS  — move arrears to the end of the loan, keeping the current instalment
                        (used when income fell, is unstable, obligations are high, or raising
                        the instalment would breach 20%).
  • MAINTAIN          — keep the current instalment unchanged.
  • Refer to officer  — complex / low-confidence cases only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEDUCTION_CAP = 0.20            # Rule 1
OBLIGATIONS_HIGH = 0.60        # total obligations / income above this → don't raise instalment
PER_MEMBER_FLOOR = 2500        # average income per family member below this → lighter plan
PLAN_HORIZONS = (12, 18, 24, 36, 48, 60, 84, 120)  # months to spread arrears; capped by term
SALARY_MISMATCH_TOL = 0.15     # declared-vs-cert salary gap that triggers human review


@dataclass
class ArrearsCase:
    application_id: str
    customer_id: str
    applicant: str
    current_salary: float          # verified monthly income (AED)
    arrears: float                 # total overdue amount (AED)
    overdue_months: float
    current_emi: float             # current monthly instalment (AED)
    original_term_months: int      # original approved repayment period (Rule 2 ceiling)
    remaining_term_months: int
    family_size: int | None = None
    dependents: int | None = None
    has_active_request: bool = False
    income_stable: bool = True
    employment: str = "employed"   # employed | self_employed | unemployed | retired
    temporary_hardship: bool = False
    obligations_ratio: float | None = None   # other monthly obligations / income
    salary_cert_provided: bool = True
    declared_salary: float | None = None      # salary stated on uploaded certificate


@dataclass
class PlanOption:
    months: int
    monthly_aed: float
    deduction_ratio: float
    within_cap: bool

    def as_dict(self) -> dict:
        return {"months": self.months, "monthly_aed": round(self.monthly_aed, 2),
                "deduction_ratio": round(self.deduction_ratio, 4), "within_cap": self.within_cap}


@dataclass
class ArrearsAssessment:
    recommendation: str            # approve | request_documents | refer_to_officer | reject
    approved_request_type: str | None   # UPDATE_INSTALLMENT | TRANSFER_ARREARS | MAINTAIN | None
    confidence: float
    proposed_emi: float | None
    proposed_term_months: int | None
    deduction_ratio: float | None
    rule_20_pass: bool
    rule_period_pass: bool
    rule_active_pass: bool
    application_complete: bool
    reasons: list[str] = field(default_factory=list)
    plan_options: list[PlanOption] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)        # fraud / data-quality flags
    status: str = "in_progress"    # in_progress|approved|rejected|request_documents|human_review

    def structured(self, case: ArrearsCase) -> dict:
        """The exact officer-grade output table the Programme expects."""
        per_member = round(case.current_salary / case.family_size, 2) if case.family_size else None
        plan = None
        if self.approved_request_type == "UPDATE_INSTALLMENT" and self.proposed_emi:
            plan = f"Raise instalment to AED {self.proposed_emi:,.0f}/month for {self.proposed_term_months} months"
        elif self.approved_request_type == "TRANSFER_ARREARS":
            plan = "Move arrears to the end of the loan; keep the current instalment unchanged"
        elif self.approved_request_type == "MAINTAIN":
            plan = "Keep the current instalment unchanged"
        return {
            "application_status": "Complete" if self.application_complete else "Incomplete",
            "case_summary": (
                f"{case.applicant} — arrears AED {case.arrears:,.0f} over {int(case.overdue_months)} "
                f"month(s); current instalment AED {case.current_emi:,.0f} on AED {case.current_salary:,.0f} salary."
            ),
            "income_analysis": {
                "monthly_salary": round(case.current_salary, 2),
                "income_stable": case.income_stable,
                "family_size": case.family_size,
                "avg_income_per_member": per_member,
                "per_member_below_floor": (per_member is not None and per_member < PER_MEMBER_FLOOR),
            },
            "arrears_amount": round(case.arrears, 2),
            "overdue_installments": int(case.overdue_months),
            "remaining_repayment_period_months": case.remaining_term_months,
            "proposed_deduction_rate": (round(self.deduction_ratio * 100, 1) if self.deduction_ratio is not None else None),
            "proposed_repayment_plan": plan,
            "rule_20_compliance": "Pass" if self.rule_20_pass else "Fail",
            "rule_period_compliance": "Pass" if self.rule_period_pass else "Fail",
            "rule_active_request": "Pass" if self.rule_active_pass else "Fail",
            "recommendation": self.recommendation,
            "approved_request_type": self.approved_request_type,
            "confidence": round(self.confidence, 3),
            "reasoning": " ".join(self.reasons),
            "flags": self.flags,
            "plan_options": [p.as_dict() for p in self.plan_options],
        }


def assess_rescheduling(case: ArrearsCase) -> ArrearsAssessment:
    reasons: list[str] = []
    flags: list[str] = []
    cap_amt = DEDUCTION_CAP * max(case.current_salary, 1.0)

    # ── Rule 3: existing active request → automatic rejection ──
    rule_active_pass = not case.has_active_request
    if case.has_active_request:
        reasons.append("An active rescheduling request already exists on this account, so a new request is automatically rejected (Rule 3).")
        return ArrearsAssessment(
            recommendation="reject", approved_request_type=None, confidence=0.97,
            proposed_emi=None, proposed_term_months=None, deduction_ratio=None,
            rule_20_pass=False, rule_period_pass=False, rule_active_pass=False,
            application_complete=True, reasons=reasons, status="rejected",
        )

    # ── Document completeness ──
    application_complete = case.salary_cert_provided and case.current_salary > 0
    if not case.salary_cert_provided:
        reasons.append("A valid salary certificate is required to verify income before a decision can be made.")
        return ArrearsAssessment(
            recommendation="request_documents", approved_request_type=None, confidence=0.6,
            proposed_emi=None, proposed_term_months=None, deduction_ratio=None,
            rule_20_pass=False, rule_period_pass=False, rule_active_pass=True,
            application_complete=False, reasons=reasons, status="request_documents",
        )

    # ── Fraud / consistency: declared salary vs certificate ──
    mismatch = False
    if case.declared_salary and case.current_salary > 0:
        gap = abs(case.declared_salary - case.current_salary) / case.current_salary
        if gap > SALARY_MISMATCH_TOL:
            mismatch = True
            flags.append(f"Salary on certificate (AED {case.declared_salary:,.0f}) differs from the verified figure by {gap:.0%}.")

    # ── Income / capacity analysis ──
    cur_ratio = case.current_emi / max(case.current_salary, 1.0)
    headroom = cap_amt - case.current_emi
    per_member = (case.current_salary / case.family_size) if case.family_size else None
    hardship = (
        case.employment in ("unemployed", "retired")
        or not case.income_stable
        or case.temporary_hardship
        or (case.obligations_ratio is not None and case.obligations_ratio > OBLIGATIONS_HIGH)
        or (per_member is not None and per_member < PER_MEMBER_FLOOR)
    )

    # ── Build UPDATE_INSTALLMENT plan options (spread arrears, stay within 20% & period) ──
    max_term = min(case.remaining_term_months or case.original_term_months, case.original_term_months)
    options: list[PlanOption] = []
    chosen: PlanOption | None = None
    if case.arrears > 0 and headroom > 0:
        for n in PLAN_HORIZONS:
            if n > max_term:
                break
            extra = case.arrears / n
            new_emi = case.current_emi + extra
            ratio = new_emi / case.current_salary
            opt = PlanOption(n, new_emi, ratio, ratio <= DEDUCTION_CAP)
            options.append(opt)
            if chosen is None and opt.within_cap:
                chosen = opt

    # ── Decision matrix ──
    confidence = 0.9
    if hardship and cur_ratio <= DEDUCTION_CAP:
        # Income fell / unstable / obligations high → don't raise instalment; move arrears to end.
        approved_type = "TRANSFER_ARREARS"
        recommendation = "approve"
        proposed_emi = case.current_emi
        proposed_term = case.remaining_term_months
        deduction_ratio = cur_ratio
        why = []
        if case.employment in ("unemployed", "retired"):
            why.append(f"income source is {case.employment}")
        if not case.income_stable:
            why.append("income is not stable")
        if case.temporary_hardship:
            why.append("a temporary hardship is documented")
        if case.obligations_ratio is not None and case.obligations_ratio > OBLIGATIONS_HIGH:
            why.append(f"existing obligations are high ({case.obligations_ratio:.0%} of income)")
        if per_member is not None and per_member < PER_MEMBER_FLOOR:
            why.append(f"average income per family member is AED {per_member:,.0f} (below AED {PER_MEMBER_FLOOR:,})")
        reasons.append(
            "Because " + ", and ".join(why) + ", raising the monthly instalment would be unfair. "
            "The arrears are moved to the end of the loan so the current instalment is unchanged."
        )
        confidence = 0.82
    elif chosen is not None:
        # Raise instalment to clear arrears, shortest plan that stays within 20%.
        approved_type = "UPDATE_INSTALLMENT"
        recommendation = "approve"
        proposed_emi = chosen.monthly_aed
        proposed_term = chosen.months
        deduction_ratio = chosen.deduction_ratio
        reasons.append(
            f"The arrears of AED {case.arrears:,.0f} can be cleared by raising the instalment to "
            f"AED {proposed_emi:,.0f}/month over {proposed_term} months. The new deduction is "
            f"{deduction_ratio:.1%} of salary — within the 20% cap — and the term stays within the "
            f"original repayment period."
        )
        # tighter margin to the cap → slightly lower confidence
        confidence = 0.93 if deduction_ratio <= 0.18 else 0.85
    elif cur_ratio <= DEDUCTION_CAP and case.arrears > 0:
        # Can't raise within 20% → move arrears to end at the current instalment.
        approved_type = "TRANSFER_ARREARS"
        recommendation = "approve"
        proposed_emi = case.current_emi
        proposed_term = case.remaining_term_months
        deduction_ratio = cur_ratio
        reasons.append(
            f"Raising the instalment enough to clear AED {case.arrears:,.0f} would exceed the 20% deduction "
            f"cap, so the arrears are moved to the end of the loan and the current instalment is kept."
        )
        confidence = 0.8
    else:
        # Current instalment already breaches the cap, or no salary → needs a human officer.
        approved_type = None
        recommendation = "refer_to_officer"
        proposed_emi = None
        proposed_term = None
        deduction_ratio = cur_ratio if case.current_salary > 0 else None
        reasons.append(
            "This case cannot be resolved automatically within policy (the current instalment already "
            "approaches or exceeds the 20% cap). Referring to a Programme officer for a tailored plan."
        )
        confidence = 0.55

    # ── Fraud / low-confidence override → human review ──
    if mismatch:
        recommendation = "refer_to_officer"
        confidence = min(confidence, 0.5)
        reasons.append("Because of the salary inconsistency, the case is referred to an officer for verification.")

    # ── Compliance flags ──
    rule_20_pass = (deduction_ratio is not None and deduction_ratio <= DEDUCTION_CAP)
    rule_period_pass = (proposed_term is None) or (proposed_term <= case.original_term_months)

    status = {
        "approve": "approved", "reject": "rejected",
        "request_documents": "request_documents", "refer_to_officer": "human_review",
    }[recommendation]

    return ArrearsAssessment(
        recommendation=recommendation, approved_request_type=approved_type, confidence=confidence,
        proposed_emi=proposed_emi, proposed_term_months=proposed_term, deduction_ratio=deduction_ratio,
        rule_20_pass=rule_20_pass, rule_period_pass=rule_period_pass, rule_active_pass=rule_active_pass,
        application_complete=application_complete, reasons=reasons, plan_options=options,
        flags=flags, status=status,
    )
