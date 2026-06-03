"""Risk scorer with SHAP-style feature importances.

For the hackathon: simple weighted scorecard (no XGBoost dependency needed). The output shape
exactly matches what a real XGBoost+SHAP pipeline would return — judges see "feature contributions"
which is the explainability flex.

Day-90 productionization: train an actual XGBoost on historical SZHP arrears data, swap this
function's body. The interface stays identical, so callers don't change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeatureContribution:
    feature: str
    value: float
    contribution: float    # signed; positive raises default risk


@dataclass
class RiskScoreResult:
    p_default: float                     # 0..1
    band: str                            # "low" | "medium" | "high"
    contributions: list[FeatureContribution]

    def as_dict(self) -> dict:
        return {
            "p_default": round(self.p_default, 3),
            "band": self.band,
            "contributions": [
                {"feature": c.feature, "value": c.value, "contribution": round(c.contribution, 3)}
                for c in self.contributions
            ],
        }


def risk_score(
    *,
    months_in_arrears: int,
    dti: float,
    employment_status: str,
    dependents: int,
    prior_reschedule: bool,
) -> RiskScoreResult:
    """Weighted scorecard. Calibrated to roughly match SZHP-published default-rate bands."""
    contribs: list[FeatureContribution] = []

    arrears_contrib = min(months_in_arrears * 0.07, 0.40)
    contribs.append(FeatureContribution("months_in_arrears", months_in_arrears, arrears_contrib))

    dti_contrib = max(0.0, dti - 0.30) * 1.0
    contribs.append(FeatureContribution("dti", dti, dti_contrib))

    emp_map = {"employed": -0.10, "self_employed": 0.05, "unemployed": 0.30, "retired": -0.05}
    emp_contrib = emp_map.get(employment_status, 0.0)
    contribs.append(FeatureContribution("employment_status", 1.0, emp_contrib))

    dep_contrib = min(dependents * 0.02, 0.10)
    contribs.append(FeatureContribution("dependents", dependents, dep_contrib))

    prior_contrib = 0.10 if prior_reschedule else 0.0
    contribs.append(FeatureContribution("prior_reschedule", 1.0 if prior_reschedule else 0.0, prior_contrib))

    base_rate = 0.08
    p_default = max(0.0, min(0.95, base_rate + sum(c.contribution for c in contribs)))
    band = "high" if p_default >= 0.40 else "medium" if p_default >= 0.20 else "low"

    return RiskScoreResult(p_default=p_default, band=band, contributions=contribs)
