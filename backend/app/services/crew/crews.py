"""Build and run the sequential crews; validate their structured outputs. Never fabricates."""
import re
from typing import TypeVar

from crewai import Crew, Process
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services import quota
from app.models.llm_outputs import ClaimEvidence, Extracted, SignalSet
from app.services.crew import agents, tasks
from app.services.crew.tools import FactCheckSearchTool, GroundedSearchTool, NewsSearchTool, ToolLedger

M = TypeVar("M", bound=BaseModel)


class CrewUnavailable(RuntimeError):
    pass


def _parse(task_output, model: type[M]) -> M:
    """`.pydantic` if CrewAI produced it; otherwise validate the raw text (code fences stripped)."""
    if isinstance(getattr(task_output, "pydantic", None), model):
        return task_output.pydantic
    raw = (getattr(task_output, "raw", "") or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    if not raw.startswith("{"):
        m = re.search(r"\{.*\}", raw, re.S)
        raw = m.group(0) if m else raw
    return model.model_validate_json(raw)


def _crew(agent_list: list, task_list: list) -> Crew:
    return Crew(agents=agent_list, tasks=task_list, process=Process.sequential, memory=False, cache=False,
                verbose=settings.DEBUG)


def _require_key() -> None:
    if not settings.GEMINI_API_KEY:
        raise CrewUnavailable("GEMINI_API_KEY is not configured")


@quota.with_fallback
def run_text_crew(text: str, rule_findings: str) -> tuple[Extracted, SignalSet]:
    """Text mode: Extractor → Trust Signal Analyst (analyst sees the extraction via task context)."""
    _require_key()
    last: Exception | None = None
    for attempt in range(2):
        retry = attempt == 1
        extractor, analyst = agents.extractor_agent(), agents.analyst_agent()
        t1 = tasks.extraction_task(extractor, text, retry=retry)
        t2 = tasks.signals_task(analyst, "(the extraction produced by the previous task, provided in your context)",
                                rule_findings, context=[t1], retry=retry)
        try:
            result = _crew([extractor, analyst], [t1, t2]).kickoff()
            return _parse(result.tasks_output[0], Extracted), _parse(result.tasks_output[-1], SignalSet)
        except (ValidationError, ValueError) as e:
            last = e  # invalid JSON → one retry with the stricter instruction
        except Exception as e:
            raise CrewUnavailable(str(e)[:300]) from e
    raise CrewUnavailable(f"invalid structured output: {str(last)[:200]}")


@quota.with_fallback
def run_image_crew(extracted: Extracted, rule_findings: str) -> SignalSet:
    """Image mode: extraction was done by the vision step, so the Analyst runs alone."""
    _require_key()
    last: Exception | None = None
    for attempt in range(2):
        analyst = agents.analyst_agent()
        t = tasks.signals_task(analyst, extracted.model_dump_json(indent=1), rule_findings, retry=attempt == 1,
                               artifact=True)
        try:
            result = _crew([analyst], [t]).kickoff()
            return _parse(result.tasks_output[-1], SignalSet)
        except (ValidationError, ValueError) as e:
            last = e
        except Exception as e:
            raise CrewUnavailable(str(e)[:300]) from e
    raise CrewUnavailable(f"invalid structured output: {str(last)[:200]}")


@quota.with_fallback
def run_claim_crew(text: str) -> tuple[ClaimEvidence, ToolLedger]:
    """Claim mode: Claim Verifier with FactCheck + Grounded tools. Returns evidence and the tool ledger."""
    _require_key()
    last: Exception | None = None
    for attempt in range(2):
        ledger = ToolLedger()
        verifier = agents.claim_verifier_agent([NewsSearchTool(ledger), FactCheckSearchTool(ledger), GroundedSearchTool(ledger)])
        t = tasks.claim_task(verifier, text, retry=attempt == 1)
        try:
            result = _crew([verifier], [t]).kickoff()
            return _parse(result.tasks_output[-1], ClaimEvidence), ledger
        except (ValidationError, ValueError) as e:
            last = e
        except Exception as e:
            raise CrewUnavailable(str(e)[:300]) from e
    raise CrewUnavailable(f"invalid structured output: {str(last)[:200]}")
