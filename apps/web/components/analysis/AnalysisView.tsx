'use client';

import { useState } from 'react';
import { useAnalysisProgress, useStartAnalysis } from '@/lib/queries/analyses';
import type { Analysis, Finding } from '@/lib/api';
import { findingAnchorId } from '@/lib/highlight';
import { verdictLine } from '@/lib/severity';
import { AnalysisProgress } from './AnalysisProgress';
import { ContractView } from './ContractView';
import { FindingCard } from './FindingCard';
import { SeveritySummary } from './SeveritySummary';
import { Uploader } from './Uploader';

/**
 * The assembly point: owns which screen is showing and the selected finding,
 * and wires the uploader, the progress screen, the contract pane and the
 * findings list together.
 */
export function AnalysisView() {
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const start = useStartAnalysis();
  const progress = useAnalysisProgress(analysisId, start.data);
  const analysis = progress.data;

  function reset() {
    start.reset();
    setAnalysisId(null);
    setSelectedId(null);
  }

  if (!analysis || start.isPending) {
    return (
      <Uploader
        error={start.error?.message ?? null}
        onAnalyze={(file) => {
          setSelectedId(null);
          start.mutate(file, { onSuccess: (created) => setAnalysisId(created.id) });
        }}
      />
    );
  }

  if (analysis.stage !== 'done') {
    return <AnalysisProgress analysis={analysis} onCancel={reset} />;
  }

  // Every clause failed is raised by the API as an error, so reaching here with
  // a failure count means a *partial* review — which changes what the findings
  // list means and therefore leads, rather than sitting under it.
  if (analysis.status === 'failed' || analysis.clauses_failed > 0) {
    return <PartialReview analysis={analysis} onRetry={reset} />;
  }

  if (analysis.findings.length === 0) {
    return <NoFindings analysis={analysis} onReset={reset} />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-none px-8 pt-6 pb-5">
        <div className="flex flex-wrap items-end gap-8">
          <div>
            <p className="text-accent-2-ink text-[11px] tracking-[0.12em] uppercase">
              Review complete
            </p>
            <h1 className="mt-1 max-w-[780px] text-[44px] leading-[1.14] font-semibold tracking-[-0.025em] text-pretty">
              {verdictLine(analysis.findings)}
            </h1>
          </div>
          <div className="ml-auto flex gap-2.5">
            <button
              type="button"
              onClick={reset}
              className="bg-accent hover:bg-accent-hover focus-visible:outline-accent rounded-md px-4 py-2.5 text-sm font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Analyze another
            </button>
          </div>
        </div>

        <SeveritySummary findings={analysis.findings} analysis={analysis} />
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-10 px-8 pb-6 lg:grid-cols-[1.15fr_1fr]">
        <section
          aria-label="Contract text"
          className="border-border flex min-h-0 flex-col border-t pt-3.5"
        >
          <div className="text-foreground-muted mb-3 flex flex-none text-[11px] tracking-[0.12em] uppercase">
            <span>The source text</span>
            <span className="ml-auto tabular-nums">{pageLine(analysis)}</span>
          </div>
          <ContractView
            text={analysis.document.text}
            findings={analysis.findings}
            selectedId={selectedId}
            onSelect={(finding: Finding) => setSelectedId(findingAnchorId(finding))}
          />
        </section>

        <section
          aria-label="Findings"
          className="border-border flex min-h-0 flex-col border-t pt-3.5"
        >
          <div className="text-foreground-muted mb-3 flex flex-none text-[11px] tracking-[0.12em] uppercase">
            <span>Findings, worst first</span>
            <span className="ml-auto tabular-nums">
              {analysis.findings.length} {analysis.findings.length === 1 ? 'finding' : 'findings'}
            </span>
          </div>
          <ul className="flex min-h-0 max-w-[500px] flex-1 flex-col gap-6 overflow-y-auto pr-2.5">
            {analysis.findings.map((finding) => {
              const anchor = findingAnchorId(finding);
              return (
                <FindingCard
                  key={anchor}
                  finding={finding}
                  isSelected={anchor === selectedId}
                  onSelect={() => setSelectedId(anchor)}
                />
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}

function NoFindings({ analysis, onReset }: { analysis: Analysis; onReset: () => void }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-8 py-14">
      <div className="max-w-[620px]">
        <p className="text-accent-ink text-[11px] tracking-[0.12em] uppercase">Review complete</p>
        <h1 className="mt-2 text-[46px] leading-[1.08] font-semibold tracking-[-0.025em] text-pretty">
          Nothing in this document matched the risk rubric.
        </h1>
        <p className="mt-5 text-[17px] leading-relaxed">
          All {analysis.clauses_total} clauses were read and none of them tripped a rule. That is a
          real answer, not a failure — but it is not a substitute for a lawyer reading it.
        </p>
        <p className="text-foreground-muted mt-4 text-[14.5px] leading-relaxed">
          The rubric covers ten categories: unlimited liability, liability caps, auto-renewal,
          unilateral termination, IP assignment, non-compete, indemnity, governing law, payment
          terms and confidentiality. Anything outside those ten is not something this tool looked
          for.
        </p>
        <button
          type="button"
          onClick={onReset}
          className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-7 rounded-md px-5 py-2.5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Analyze another
        </button>
      </div>
    </div>
  );
}

function PartialReview({ analysis, onRetry }: { analysis: Analysis; onRetry: () => void }) {
  const failed = analysis.clauses_failed;
  const total = analysis.clauses_total;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-8 py-14">
      <div className="max-w-[620px]">
        <p className="text-accent-2-ink text-[11px] tracking-[0.12em] uppercase">
          The review stopped short
        </p>
        <h1 className="mt-2 text-[46px] leading-[1.08] font-semibold tracking-[-0.025em] text-pretty tabular-nums">
          {failed} of {total} clauses could not be read.
        </h1>
        <p className="mt-5 text-[17px] leading-relaxed">
          This document was only partly reviewed, so treat what came back as incomplete rather than
          as a clean result. {total - failed} clauses were analysed; the rest hit a provider error
          and were skipped.
        </p>
        {analysis.error && (
          <p className="border-accent-2 text-foreground-muted mt-4 border-l pl-3.5 text-[14.5px] leading-relaxed italic">
            {analysis.error}
          </p>
        )}
        <button
          type="button"
          onClick={onRetry}
          className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-7 rounded-md px-5 py-2.5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Start again
        </button>
      </div>
    </div>
  );
}

function pageLine(analysis: Analysis): string {
  const count = analysis.document.page_count;
  if (count === null) return `${analysis.clauses_total} clauses`;
  return count === 1 ? 'Page 1' : `Pages 1–${count}`;
}
