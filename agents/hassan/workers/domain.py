"""Per-domain workers — energy, transport, maritime, infrastructure.

Same pattern as the General worker, scoped to a single MOEI service domain.
These are real responders, not stubs. They use the MOEI catalog for grounding.
"""

from __future__ import annotations

from .general import GeneralWorkerResult, run_general_agent


async def run_energy_agent(*, text: str, language: str, memory_snippets: list[str] | None = None) -> GeneralWorkerResult:
    """Electricity & water tariffs, outages, petroleum-trading licences."""
    primed = f"[domain hint: energy] {text}"
    return await run_general_agent(text=primed, language=language, memory_snippets=memory_snippets)


async def run_transport_agent(*, text: str, language: str, memory_snippets: list[str] | None = None) -> GeneralWorkerResult:
    """National transportation permits, vehicle registrations."""
    primed = f"[domain hint: transport] {text}"
    return await run_general_agent(text=primed, language=language, memory_snippets=memory_snippets)


async def run_maritime_agent(*, text: str, language: str, memory_snippets: list[str] | None = None) -> GeneralWorkerResult:
    """Pleasure boats, seafarer certificates, vessel permits."""
    primed = f"[domain hint: maritime] {text}"
    return await run_general_agent(text=primed, language=language, memory_snippets=memory_snippets)


async def run_infrastructure_agent(*, text: str, language: str, memory_snippets: list[str] | None = None) -> GeneralWorkerResult:
    """Federal infrastructure permits, geological data requests."""
    primed = f"[domain hint: infrastructure] {text}"
    return await run_general_agent(text=primed, language=language, memory_snippets=memory_snippets)


async def run_complaints_agent(*, text: str, language: str, memory_snippets: list[str] | None = None) -> GeneralWorkerResult:
    """Dedicated complaints handler in the multi-agent ecosystem.

    De-escalates with empathy, acknowledges the grievance, assures the citizen a tracked
    case is opened and (when severe) a human officer is assigned. Coordinated by the
    supervisor (master agent) like the service workers.
    """
    primed = (
        "[role: MOEI complaints officer] A citizen is raising a complaint or grievance. "
        "Acknowledge their frustration sincerely and briefly, confirm a tracked case is being "
        "opened, state the concrete next step and expected timeframe, and offer a human officer "
        "if they prefer. Do not be defensive. Keep it warm and under 100 words.\n\n"
        f"Citizen message: {text}"
    )
    return await run_general_agent(text=primed, language=language, memory_snippets=memory_snippets)
