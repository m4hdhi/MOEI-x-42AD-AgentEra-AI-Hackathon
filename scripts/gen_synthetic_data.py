"""Generate synthetic SZHP rescheduling cases + salary-slip text files.

Usage:
    uv run python scripts/gen_synthetic_data.py --cases 300 --slips 100

Outputs to data/synthetic/. All PDPL-safe — fabricated Emirati names + valid-format
Emirates IDs that are NOT real assignments. Numbers are within realistic SZHP ranges.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    print("faker not installed; run: uv pip install faker")
    raise SystemExit(1)


OUT = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def emirates_id(year: int, seq: int) -> str:
    # Real EIDs include a check digit; the last digit here is a placeholder.
    return f"784-{year}-{seq:07d}-0"


def make_case(fake_en: Faker, fake_ar: Faker, idx: int) -> dict:
    yob = random.randint(1955, 2000)
    eid = emirates_id(yob, idx)
    employed = random.choices(["employed", "self_employed", "unemployed", "retired"], weights=[60, 15, 15, 10])[0]
    income = (
        random.randint(0, 4000) if employed == "unemployed"
        else random.randint(15_000, 35_000) if employed == "retired"
        else random.randint(8_000, 60_000)
    )
    months_arrears = random.choices(range(0, 12), weights=[20, 15, 12, 10, 9, 8, 7, 6, 5, 3, 3, 2])[0]
    balance = random.randint(80_000, 1_500_000)
    installment = round(balance / random.randint(120, 300), 0)
    return {
        "case_id": f"HSG-{idx:05d}",
        "emirates_id": eid,
        "full_name_en": fake_en.name(),
        "full_name_ar": fake_ar.name(),
        "age": 2026 - yob,
        "employment_status": employed,
        "monthly_income_aed": income,
        "monthly_installment_aed": installment,
        "outstanding_balance_aed": balance,
        "months_in_arrears": months_arrears,
        "dependents": random.randint(0, 6),
        "has_prior_reschedule": random.random() < 0.18,
        "channel_first_contact": random.choice(["whatsapp", "voice", "web", "branch"]),
    }


SLIP_TEMPLATE = """\
SHEIKH ZAYED HOUSING PROGRAMME — APPLICANT SALARY SLIP
======================================================
Employer: {employer}
Employee: {name}
Emirates ID: {eid}
Pay Period: {period}

Basic Salary (Gross):   AED {gross:,.2f}
Allowances:             AED {allow:,.2f}
Deductions:             AED {deduct:,.2f}
-------------------------------------------
Net Salary (Take-Home): AED {net:,.2f}

This is a synthetic document for hackathon demonstration. PDPL-safe.
"""


def make_slip(fake_en: Faker, idx: int, case: dict) -> str:
    gross = case["monthly_income_aed"] * random.uniform(1.05, 1.20)
    allow = gross * random.uniform(0.05, 0.15)
    deduct = gross * random.uniform(0.05, 0.10)
    net = gross + allow - deduct
    return SLIP_TEMPLATE.format(
        employer=fake_en.company(),
        name=case["full_name_en"],
        eid=case["emirates_id"],
        period="2026-04",
        gross=gross,
        allow=allow,
        deduct=deduct,
        net=net,
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=int, default=300)
    p.add_argument("--slips", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    Faker.seed(args.seed)
    fake_en = Faker("en_US")
    fake_ar = Faker("ar_AA")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "salary_slips").mkdir(exist_ok=True)

    cases = [make_case(fake_en, fake_ar, i + 1) for i in range(args.cases)]
    (OUT / "cases.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases))

    for i, case in enumerate(cases[: args.slips]):
        (OUT / "salary_slips" / f"{case['case_id']}.txt").write_text(make_slip(fake_en, i, case))

    print(f"Wrote {len(cases)} cases to {OUT / 'cases.jsonl'}")
    print(f"Wrote {args.slips} salary slips to {OUT / 'salary_slips'}")


if __name__ == "__main__":
    main()
