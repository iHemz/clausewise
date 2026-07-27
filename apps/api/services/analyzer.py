"""The analysis pipeline: clause → Claude → grounded findings → judged severity.

Two model passes, deliberately separated:

1. **Analyze** — for each clause, identify risks against a fixed rubric and
   quote the exact text being flagged.
2. **Judge** — a second, independent call re-scores severity from the clause
   text alone, without seeing the first model's reasoning. Severity drives what
   a reviewer reads first, so having one model's guess be the only input to
   that ordering is a weak spot; an independent second opinion makes
   disagreement visible instead of hidden.

Between the two sits the grounding gate: any finding whose quote cannot be
located in the clause it claims to describe is **dropped**, not shown with an
approximate span. That rule is the product. A citation a lawyer cannot click
through to is not a citation, and a tool that fabricates one is worse than no
tool at all.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from core import llm
from core.errors import UpstreamError
from core.providers import Provider
from domain.contracts import (
    Clause,
    Finding,
    RiskCategory,
    Severity,
    ground_finding,
    sort_findings,
)

logger = logging.getLogger("clausewise.analyzer")

# Clause analysis is I/O-bound and independent per clause, so the wall-clock
# cost is closer to one round trip than to N. Kept low deliberately: pushing it
# higher measurably increases 529 Overloaded responses, and a retried request
# costs more wall-clock time than the parallelism saved.
MAX_CONCURRENCY = 4


# --- Schemas the model is constrained to ----------------------------------
# Defined before the prompts, on purpose: the schema is the contract, and the
# prompt only has to explain the judgement. Because the API enforces these
# server-side, there is no fence-stripping, no brace-trimming, and no
# "the model wrote a sentence after the JSON" failure mode to handle.


class RawFinding(BaseModel):
    """One risk as the analyzer reports it, before grounding."""

    title: str = Field(description="A short label for the risk, e.g. 'Uncapped indemnity'.")
    category: RiskCategory
    severity: Severity
    reason: str = Field(description="One sentence on why this is risky, in plain English.")
    suggested_rewrite: str = Field(description="A safer replacement for the clause text.")
    quote: str = Field(
        description=(
            "The EXACT contract text this finding is about, copied verbatim from "
            "the clause. Must appear character-for-character in the clause."
        )
    )


class ClauseAnalysis(BaseModel):
    findings: list[RawFinding] = Field(
        description="Risks found in this clause. Empty when the clause is unremarkable."
    )


class SeverityJudgement(BaseModel):
    severity: Severity
    note: str = Field(description="One sentence justifying the severity.")


# --- Prompts ---------------------------------------------------------------

ANALYZER_SYSTEM = """\
You are a contract review assistant working for the party who is being asked to \
sign. You read one clause at a time and flag terms that expose that party to \
risk.

Score only against these categories:
- unlimited_liability — liability that is uncapped or capped far above contract value
- limitation_of_liability — a cap so low it makes remedies meaningless
- auto_renewal — renews automatically, especially with a short or awkward notice window
- unilateral_termination — one side may terminate or vary terms at will
- ip_assignment — IP ownership transfers more broadly than the work being paid for
- non_compete — restricts future work by scope, geography, or duration
- indemnity — one-sided or uncapped duty to indemnify
- governing_law — jurisdiction or venue that is impractical or hostile for the signer
- payment_terms — long payment windows, unilateral offset, or punitive late terms
- confidentiality — obligations that are perpetual, one-sided, or overly broad

Rules that matter more than coverage:

1. QUOTE EXACTLY. The `quote` field must be text copied character-for-character \
from the clause you were given. Do not paraphrase, do not tidy punctuation, do \
not merge two separate sentences. If you cannot quote it, do not report it.
2. Quote the specific operative words, not the whole clause. One or two \
sentences is right; a whole page is not.
3. Report nothing when the clause is ordinary. An empty list is a correct and \
expected answer. Do not manufacture a finding to seem useful.
4. `reason` is one plain-English sentence a non-lawyer understands. No legalese, \
no hedging, no restating the clause.
5. `suggested_rewrite` is replacement contract language, not advice about what to \
do. Write the words that should go in the document.

Severity:
- high — could cause uncapped or business-threatening loss, or gives away \
something very hard to get back
- medium — meaningfully unfavourable and worth negotiating
- low — worth knowing about, but standard or minor\
"""

JUDGE_SYSTEM = """\
You are a second reviewer scoring the severity of one contract risk. You are \
given the clause text and the specific risk that was flagged. You are NOT given \
the first reviewer's severity — score it independently.

- high — could cause uncapped or business-threatening loss, or gives away \
something very hard to get back
- medium — meaningfully unfavourable and worth negotiating
- low — worth knowing about, but standard or minor

Judge the commercial exposure to the party signing this contract, not how \
unusual the drafting is. Boilerplate that is genuinely dangerous is still high; \
unusual wording that costs nothing is still low.\
"""


@dataclass
class DocumentResult:
    """The outcome of analyzing a whole document."""

    findings: list[Finding] = field(default_factory=list)
    dropped: int = 0
    #: Clauses whose analysis call failed. Partial failure still returns a
    #: result, but the count travels with it so the UI can say so.
    clauses_failed: int = 0
    #: Every model provider that served part of this analysis. More than one
    #: means a mid-run failover, which the reader deserves to know about:
    #: severity calibration differs between models, so a document reviewed by
    #: two of them is not the same artifact as one reviewed by either alone.
    providers_used: set[str] = field(default_factory=set)


@dataclass
class ClauseResult:
    """What one clause's analysis produced, including whether it failed at all.

    ``failed`` is tracked separately from an empty ``findings`` list because the
    two mean opposite things: an unremarkable clause legitimately yields no
    findings, whereas a failed call yields none because nothing was reviewed.
    Collapsing them is how a missing API key turns into a confident
    "no risks found".
    """

    findings: list[Finding]
    dropped: int = 0
    failed: bool = False
    #: Which provider answered, when one did.
    provider: Provider | None = None


def analyze_clause(clause: Clause, page_breaks: list[int]) -> ClauseResult:
    """Analyze one clause and ground every finding it produces.

    Failures are contained to the clause — a single bad response should cost one
    clause, not the document — but they are *recorded*, so the caller can tell
    the difference between a quiet contract and a broken pipeline.
    """
    prompt = (
        "Review this contract clause and report any risks against the rubric.\n\n"
        f'<clause id="{clause.id}">\n{clause.text}\n</clause>'
    )

    try:
        completion = llm.parse_meta(
            prompt=prompt,
            schema=ClauseAnalysis,
            system=ANALYZER_SYSTEM,
            # The system prompt is identical across every clause in every
            # document, so caching it turns most of the input cost into
            # cache reads.
            cache_system=True,
            max_tokens=4000,
        )
    except Exception:
        logger.exception("clause_analysis_failed", extra={"clause_id": clause.id})
        return ClauseResult(findings=[], failed=True)

    analysis = completion.value
    provider = completion.usage.provider

    findings: list[Finding] = []
    dropped = 0

    for raw in analysis.findings:
        citation = ground_finding(clause=clause, quote=raw.quote, page_breaks=page_breaks)
        if citation is None:
            # The model described something it could not point to. Drop it.
            dropped += 1
            logger.info(
                "finding_dropped_ungrounded",
                extra={"clause_id": clause.id, "quote": raw.quote[:120]},
            )
            continue

        findings.append(
            Finding(
                clause_id=clause.id,
                title=raw.title,
                category=raw.category,
                severity=raw.severity,
                reason=raw.reason,
                suggested_rewrite=raw.suggested_rewrite,
                citation=citation,
            )
        )

    return ClauseResult(findings=findings, dropped=dropped, provider=provider)


def judge_finding(finding: Finding, clause_text: str) -> Finding:
    """Re-score one finding's severity with an independent call.

    Returns the finding annotated with the judge's verdict. The original
    severity is never overwritten — disagreement is information the reviewer
    should see, not something to average away.
    """
    prompt = (
        f"<clause>\n{clause_text}\n</clause>\n\n"
        f"<flagged_risk>\n"
        f"Category: {finding.category.value}\n"
        f"Concern: {finding.reason}\n"
        f"Text at issue: {finding.citation.quote}\n"
        f"</flagged_risk>\n\n"
        "How severe is this risk for the party signing?"
    )

    try:
        judgement = llm.parse(
            prompt=prompt,
            schema=SeverityJudgement,
            system=JUDGE_SYSTEM,
            cache_system=True,
            max_tokens=1000,
        )
    except Exception:
        # A failed judge pass costs the second opinion on one finding, not the
        # finding itself — the analyzer's severity stands, unannotated.
        logger.exception("judge_failed", extra={"clause_id": finding.clause_id})
        return finding

    return finding.model_copy(
        update={"judge_severity": judgement.severity, "judge_note": judgement.note}
    )


def analyze_document(
    clauses: list[Clause],
    page_breaks: list[int],
    *,
    judge: bool = True,
) -> DocumentResult:
    """Run the full pipeline over every clause.

    Raises ``UpstreamError`` when *every* clause failed. Returning an empty
    result there would be the worst possible outcome for this product: the user
    would read "no risks found" from a run in which nothing was actually
    reviewed. A missing API key, an expired key, or a total outage must look
    like a failure, not like a clean bill of health.
    """
    if not clauses:
        return DocumentResult(findings=[])

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        results = list(pool.map(lambda c: analyze_clause(c, page_breaks), clauses))

    failed = sum(1 for result in results if result.failed)
    if failed == len(clauses):
        raise UpstreamError(
            f"Every one of the {len(clauses)} clauses failed to analyze. "
            "The model could not be reached — check ANTHROPIC_API_KEY and the "
            "service status. No conclusions can be drawn from this document."
        )

    findings = [finding for result in results for finding in result.findings]
    dropped = sum(result.dropped for result in results)
    providers = {r.provider.value for r in results if r.provider is not None}

    if len(providers) > 1:
        # Worth a warning, not just a field: two models with different severity
        # calibration each reviewed part of one document.
        logger.warning("mixed_provider_analysis", extra={"providers": sorted(providers)})

    if judge and findings:
        clause_text_by_id = {clause.id: clause.text for clause in clauses}
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            findings = list(
                pool.map(
                    lambda f: judge_finding(f, clause_text_by_id.get(f.clause_id, "")),
                    findings,
                )
            )

    return DocumentResult(
        findings=sort_findings(findings),
        dropped=dropped,
        clauses_failed=failed,
        providers_used=providers,
    )
