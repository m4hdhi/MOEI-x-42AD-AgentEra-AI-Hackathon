"""LLM client cascade — OpenAI/Claude → Groq → Gemini (all cloud, no local model).

Built on LangChain chat models so we get .with_structured_output() and tool-binding for free.
Groq is OpenAI-compatible, so we use ChatOpenAI pointed at api.groq.com.

Roles instead of model names: callers ask for what they NEED (a router, a critic, an arabic
composer), and routing policy lives here. Lets us swap Groq→Cerebras for the 5 demo minutes
without touching node code.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from loguru import logger


class LLMRole(StrEnum):
    ROUTER = "router"            # fast intent + service classifier
    REASONER = "reasoner"        # main planner / dispatcher reasoning
    CRITIC = "critic"            # separate model for Reflection node
    COMPOSER = "composer"        # final response generation
    ARABIC = "arabic"            # Khaliji-aware Arabic turns → Jais
    LONGCTX = "longctx"          # multimodal / long-context (Docling outputs, dashboard queries)
    FAST_LOCAL = "fast_local"    # legacy alias; now points to Groq 8B (no local model)


# ---- Builders ----------------------------------------------------------------

def _groq_llama_70b(*, temperature: float = 0.2) -> BaseChatModel:
    """Groq llama-3.3-70b-versatile — high quality, ~15-25s per call."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=temperature,
        max_tokens=1024,
        timeout=20,
        max_retries=1,
    )


def _groq_llama_8b_instant(*, temperature: float = 0.2) -> BaseChatModel:
    """Groq llama-3.1-8b-instant — ~5× faster than 70b. Used for Router (cheap classification).

    Per Groq's docs the 8b model runs at ~750 tokens/sec vs 250 for 70b. For Router-style
    structured-output tasks (intent + service + confidence), 8b is plenty accurate.
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return ChatOpenAI(
        model="llama-3.1-8b-instant",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=temperature,
        max_tokens=512,
        timeout=15,
        max_retries=1,
    )


def _gemini_flash(*, temperature: float = 0.2) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=temperature,
    )


def _jais_hf(*, temperature: float = 0.2) -> BaseChatModel:
    """Jais-Family-30B-chat via HF Inference (OpenAI-compatible router)."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("HUGGINGFACE_API_TOKEN")
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_TOKEN is not set")
    return ChatOpenAI(
        model="inception/jais-family-30b-chat",
        api_key=api_key,
        base_url="https://router.huggingface.co/v1",
        temperature=temperature,
        max_tokens=1024,
        timeout=30,
    )


def _openai_chat(*, temperature: float = 0.3) -> BaseChatModel:
    """OpenAI GPT-4o-mini — fast, cheap, quality.

    ~$0.15/M input tokens, ~$0.60/M output. ~$0.001 per Hassan turn.
    Used as the quality answering brain when OPENAI_API_KEY is set.
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        temperature=temperature,
        max_tokens=1024,
        timeout=20,
        max_retries=1,
    )


def _claude_sonnet(*, temperature: float = 0.3) -> BaseChatModel:
    """Anthropic Claude Sonnet 4.6 — the quality answering brain.

    Used for General/Composer/Critic. Materially better than Llama 3.3 70B at federal-style
    customer service Q&A (citations, refusals, instruction following) and roughly the same
    latency (~5-10s warm).
    """
    from langchain_anthropic import ChatAnthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return ChatAnthropic(
        model_name="claude-sonnet-4-6",       # latest Sonnet at time of build
        api_key=api_key,
        temperature=temperature,
        max_tokens_to_sample=1024,
        timeout=30,
        max_retries=1,
    )


# ---- Role → model mapping ----------------------------------------------------

@lru_cache(maxsize=16)
def get_llm(role: LLMRole, *, temperature: float = 0.2) -> BaseChatModel:
    """Return the configured model for a role. Cached so we reuse HTTP clients.

    Routing policy (May 2026, all cloud, no local):
    - Router → Groq Llama 3.1 8B Instant (cheap classification, ~5× faster than 70B)
    - Reasoner/Composer/Critic → OpenAI gpt-4o-mini (preferred) → Claude Sonnet 4.6
      (if HASSAN_USE_CLAUDE=1 and OPENAI not set) → Groq Llama 3.3 70B (last fallback)
    - Arabic → Jais (Khaliji-aware) → Gemini fallback → Groq 70B last fallback
    - Long-context multimodal → Gemini 2.5 Flash → Groq 70B last fallback
    """
    match role:
        case LLMRole.ROUTER:
            try:
                return _groq_llama_8b_instant(temperature=temperature)
            except RuntimeError:
                return _groq_llama_70b(temperature=temperature)

        case LLMRole.REASONER | LLMRole.COMPOSER | LLMRole.CRITIC:
            # Quality cascade — pick whichever is configured, prefer OpenAI > Claude > Groq.
            if os.getenv("OPENAI_API_KEY"):
                try:
                    return _openai_chat(temperature=temperature)
                except RuntimeError:
                    pass
            if os.getenv("HASSAN_USE_CLAUDE") == "1":
                try:
                    return _claude_sonnet(temperature=temperature)
                except RuntimeError:
                    pass
            return _groq_llama_70b(temperature=temperature)

        case LLMRole.ARABIC:
            try:
                return _jais_hf(temperature=temperature)
            except RuntimeError:
                try:
                    return _gemini_flash(temperature=temperature)
                except RuntimeError:
                    return _groq_llama_70b(temperature=temperature)

        case LLMRole.LONGCTX:
            try:
                return _gemini_flash(temperature=temperature)
            except RuntimeError:
                return _groq_llama_70b(
                    temperature=temperature,
                )

        case LLMRole.FAST_LOCAL:
            # Kept as an enum value for API compatibility but no longer routes to Ollama.
            return _groq_llama_8b_instant(temperature=temperature)


def get_llm_with_fallback(role: LLMRole, **kw: Any) -> BaseChatModel:
    """Return a LangChain Runnable that auto-falls-back across cloud providers.

    All cloud, no local model. The Groq 70B fallback handles transient OpenAI/Anthropic errors.
    """
    primary = get_llm(role, **kw)
    fallbacks: list[BaseChatModel] = []

    if role in (LLMRole.REASONER, LLMRole.COMPOSER, LLMRole.CRITIC):
        try:
            groq = _groq_llama_70b(temperature=kw.get("temperature", 0.2))
            if groq is not primary:
                fallbacks.append(groq)
        except RuntimeError:
            pass

    if not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks)
