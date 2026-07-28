'use client';

import { useState } from 'react';
import { useAnalysisProgress, useStartAnalysis } from '@/lib/queries/analyses';
import type { Analysis, Finding } from '@/lib/api';
import { findingAnchorId, findingKey } from '@/lib/highlight';
import { verdictLine } from '@/lib/severity';
import { useIsNarrow } from '@/lib/use-narrow';
import { cn } from '@/lib/utils';
import { AnalysisProgress } from './AnalysisProgress';
import { ContractView } from './ContractView';
import { FindingCard } from './FindingCard';
import { SeveritySummary } from './SeveritySummary';
import { Uploader } from './Uploader';

/**
 * The assembly point: owns which screen is showing and the selected finding,
 * and wires the uploader, the progress screen, the contract pane and the
 * findings list together.
 *
 * Two layouts, not one that shrinks. Wide: contract and findings side by side,
 * each pane its own scroller inside a fixed-height shell. Narrow: one page
 * scroll, the two put behind tabs, and a finding offers to take you to its
 * citation rather than expecting you to track it in a small window.
 */
export function AnalysisView() {
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<'findings' | 'contract'>('findings');
  const narrow = useIsNarrow();

  const start = useStartAnalysis();
  const progress = useAnalysisProgress(analysisId, start.data);
  const analysis = progress.data;

  function reset() {
    start.reset();
    setAnalysisId(null);
    setSelectedId(null);
    setTab('findings');
  }

  /** Narrow only: show the contract tab and bring the citation into view. */
  function jumpToCitation(finding: Finding) {
    const anchor = findingAnchorId(finding);
    setSelectedId(anchor);
    setTab('contract');
    requestAnimationFrame(() => {
      const el = document.querySelector<HTMLElement>(`[data-anchor="${anchor}"]`);
      if (!el) return;
      const top = el.getBoundingClientRect().top + window.scrollY - window.innerHeight / 3;
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    });
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

  // Every clause failing is raised by the API as an error, so reaching here
  // with a failure count means a *partial* review — which changes what the
  // findings list means and therefore leads, rather than sitting under it.
  if (analysis.status === 'failed' || analysis.clauses_failed > 0) {
    return <PartialReview analysis={analysis} onRetry={reset} />;
  }

  if (analysis.findings.length === 0) {
    return <NoFindings analysis={analysis} onReset={reset} />;
  }

  const showContract = !narrow || tab === 'contract';
  const showFindings = !narrow || tab === 'findings';

  return (
    <div className="flex w-full flex-col lg:min-h-0 lg:flex-1">
      <div className="flex-none px-[clamp(18px,3vw,34px)] pt-6 pb-4.5">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          <div className="min-w-0">
            <p className="text-accent-2-ink text-[11px] tracking-[0.12em] uppercase">
              Review complete
            </p>
            <h1 className="mt-1 max-w-[22ch] text-[clamp(28px,4.2vw,44px)] leading-[1.12] font-semibold tracking-[-0.025em] text-pretty">
              {verdictLine(analysis.findings)}
            </h1>
          </div>
          <div className="ml-auto flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={reset}
              className="bg-accent hover:bg-accent-hover focus-visible:outline-accent min-h-11 rounded-md px-4 py-2.5 text-sm font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Analyze another
            </button>
          </div>
        </div>

        <SeveritySummary findings={analysis.findings} analysis={analysis} />
      </div>

      {narrow && (
        <div role="tablist" className="border-border bg-surface sticky top-0 z-10 flex border-y">
          <Tab selected={tab === 'findings'} onClick={() => setTab('findings')}>
            Findings ({analysis.findings.length})
          </Tab>
          <Tab selected={tab === 'contract'} onClick={() => setTab('contract')}>
            The contract
          </Tab>
        </div>
      )}

      <div className="block px-[clamp(18px,3vw,34px)] pt-4.5 pb-10 lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-[clamp(28px,3vw,56px)] lg:pt-0 lg:pb-6">
        {showContract && (
          <section
            aria-label="Contract text"
            className="border-border block lg:flex lg:min-h-0 lg:flex-col lg:border-t lg:pt-3.5"
          >
            <div className="text-foreground-muted mb-3 flex flex-none gap-3 text-[11px] tracking-[0.12em] uppercase">
              <span>The source text</span>
              <span className="ml-auto whitespace-nowrap tabular-nums">{pageLine(analysis)}</span>
            </div>
            <ContractView
              text={analysis.document.text}
              findings={analysis.findings}
              selectedId={selectedId}
              scrolls={!narrow}
              onSelect={(finding: Finding) => setSelectedId(findingAnchorId(finding))}
            />
          </section>
        )}

        {showFindings && (
          <section
            aria-label="Findings"
            className="border-border block lg:flex lg:min-h-0 lg:flex-col lg:border-t lg:pt-3.5"
          >
            <div className="text-foreground-muted mb-3 hidden flex-none gap-3 text-[11px] tracking-[0.12em] uppercase lg:flex">
              <span>Findings, worst first</span>
              <span className="ml-auto whitespace-nowrap tabular-nums">
                {analysis.findings.length} {analysis.findings.length === 1 ? 'finding' : 'findings'}
              </span>
            </div>
            <ul className="flex flex-col gap-8 lg:min-h-0 lg:flex-1 lg:gap-6 lg:overflow-y-auto lg:pr-2.5">
              {analysis.findings.map((finding) => {
                const anchor = findingAnchorId(finding);
                return (
                  <FindingCard
                    // Key by the finding, anchor by the span — two findings can
                    // quote the same words and would otherwise share a key.
                    key={findingKey(finding)}
                    finding={finding}
                    isSelected={anchor === selectedId}
                    onSelect={() => setSelectedId(anchor)}
                    onJumpToCitation={narrow ? () => jumpToCitation(finding) : undefined}
                  />
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

function Tab({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onClick}
      className={cn(
        'min-h-[46px] flex-1 border-b-2 px-2.5 py-3 text-[13px] font-semibold tracking-[0.06em] uppercase transition-colors',
        selected ? 'border-accent text-accent-ink' : 'text-foreground-muted border-transparent',
      )}
    >
      {children}
    </button>
  );
}

function NoFindings({ analysis, onReset }: { analysis: Analysis; onReset: () => void }) {
  return (
    <div className="px-[clamp(18px,3vw,34px)] py-[clamp(34px,6vw,60px)] lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
      <div className="max-w-[62ch]">
        <p className="text-accent-ink text-[11px] tracking-[0.12em] uppercase">Review complete</p>
        <h1 className="mt-2 text-[clamp(28px,4.4vw,46px)] leading-[1.08] font-semibold tracking-[-0.025em] text-pretty">
          Nothing in this document matched the risk rubric.
        </h1>
        <p className="mt-5 text-[clamp(15px,1.3vw,17px)] leading-relaxed">
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
          className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-7 min-h-11 rounded-md px-5 py-2.5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
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
    <div className="px-[clamp(18px,3vw,34px)] py-[clamp(34px,6vw,60px)] lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
      <div className="max-w-[62ch]">
        <p className="text-accent-2-ink text-[11px] tracking-[0.12em] uppercase">
          The review stopped short
        </p>
        <h1 className="mt-2 text-[clamp(28px,4.4vw,46px)] leading-[1.08] font-semibold tracking-[-0.025em] text-pretty tabular-nums">
          {failed} of {total} clauses could not be read.
        </h1>
        <p className="mt-5 text-[clamp(15px,1.3vw,17px)] leading-relaxed">
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
          className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-7 min-h-11 rounded-md px-5 py-2.5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
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
