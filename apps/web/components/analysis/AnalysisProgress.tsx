'use client';

import { useEffect, useState } from 'react';
import type { Analysis, AnalysisStage, Finding } from '@/lib/api';
import { SEVERITY_INK, SEVERITY_LABEL } from '@/lib/severity';
import { categoryLabel, findingKey } from '@/lib/highlight';
import { cn } from '@/lib/utils';

/**
 * The wait, made legible.
 *
 * Everything here is reported by the server (`stage`, `clauses_done`,
 * `clauses_total`) rather than estimated on a timer. A progress bar that
 * advances on its own is a lie the first time a provider rate-limits, and this
 * product's whole argument is that it does not tell you things it cannot show
 * you.
 */

const ORDER: AnalysisStage[] = ['extracting', 'segmenting', 'analyzing', 'judging'];

type Status = 'done' | 'running' | 'queued';

interface Props {
  analysis: Analysis;
  onCancel: () => void;
}

export function AnalysisProgress({ analysis, onCancel }: Props) {
  const elapsed = useElapsed();
  const { stage, clauses_done: done, clauses_total: total, findings } = analysis;
  const reached = stage === 'done' ? ORDER.length : ORDER.indexOf(stage);

  const statusOf = (index: number): Status =>
    index < reached ? 'done' : index === reached ? 'running' : 'queued';

  const stages = [
    {
      num: '01',
      label: 'Text extracted',
      detail:
        statusOf(0) === 'done'
          ? `${analysis.document.text.length.toLocaleString()} characters · ${pages(analysis)} · offsets preserved`
          : 'Reading the file…',
      pct: statusOf(0) === 'done' ? 1 : 0,
    },
    {
      num: '02',
      label: 'Clauses segmented',
      detail:
        statusOf(1) === 'done'
          ? `${total} clauses found by numbering`
          : statusOf(1) === 'queued'
            ? 'Waiting on extraction'
            : 'Splitting by numbering, then headings…',
      pct: statusOf(1) === 'done' ? 1 : 0,
    },
    {
      num: '03',
      label: 'Risk pass',
      detail:
        statusOf(2) === 'queued'
          ? 'Waiting on segmentation'
          : `${done} of ${total} · ${findings.length} ${findings.length === 1 ? 'finding' : 'findings'} so far`,
      pct: total > 0 ? done / total : 0,
    },
    {
      num: '04',
      label: 'Second opinion',
      detail:
        statusOf(3) === 'done'
          ? 'Every severity re-scored'
          : statusOf(3) === 'queued'
            ? 'Runs once every clause is read'
            : 'Re-scoring each finding from the clause alone…',
      pct: statusOf(3) === 'done' ? 1 : statusOf(3) === 'running' ? 0.5 : 0,
    },
  ];

  return (
    <div className="flex w-full flex-col lg:min-h-0 lg:flex-1">
      <div className="border-border flex-none border-b px-[clamp(18px,3vw,34px)] py-6">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          <div className="min-w-0">
            <p className="text-accent-2-ink text-[11px] tracking-[0.12em] uppercase">
              Reviewing now
            </p>
            <h1 className="mt-1.5 text-[clamp(26px,4vw,40px)] leading-[1.1] font-semibold tracking-[-0.025em] tabular-nums">
              {headline(analysis)}
            </h1>
          </div>

          <div className="ml-auto text-right">
            <p className="text-foreground-muted text-[11px] tracking-[0.12em] uppercase">Elapsed</p>
            <p className="text-[22px] font-semibold tabular-nums">{elapsed}s</p>
          </div>

          <button
            type="button"
            onClick={onCancel}
            className="border-border hover:bg-foreground/5 focus-visible:outline-accent min-h-11 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Cancel
          </button>
        </div>

        <ol className="mt-6 grid gap-[clamp(20px,2.5vw,40px)] sm:grid-cols-2 lg:grid-cols-4">
          {stages.map((s, index) => {
            const status = statusOf(index);
            return (
              <li key={s.num}>
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      'text-[13px] font-semibold tabular-nums',
                      status === 'running'
                        ? 'text-accent-2-ink'
                        : status === 'done'
                          ? 'text-accent-ink'
                          : 'text-foreground-muted',
                    )}
                  >
                    {s.num}
                  </span>
                  <span
                    className={cn(
                      'text-[11px] tracking-[0.12em] uppercase',
                      status === 'running'
                        ? 'text-accent-2-ink'
                        : status === 'done'
                          ? 'text-accent-ink'
                          : 'text-foreground-muted',
                    )}
                  >
                    {status}
                  </span>
                </div>
                <p className="mt-1 text-[18px] font-semibold tracking-[-0.01em]">{s.label}</p>
                <p className="text-foreground-muted mt-0.5 text-[13.5px] leading-snug tabular-nums">
                  {s.detail}
                </p>
                <div className="bg-foreground/15 mt-2.5 h-0.5">
                  <div
                    className={cn(
                      'h-0.5 transition-[width] duration-500',
                      status === 'running' ? 'bg-accent-2' : 'bg-accent',
                    )}
                    style={{ width: `${Math.round(s.pct * 100)}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="block px-[clamp(18px,3vw,34px)] py-6 lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[1.15fr_1fr] lg:gap-[clamp(28px,3vw,56px)]">
        <section
          aria-label="Extracted contract text"
          className="block lg:flex lg:min-h-0 lg:flex-col"
        >
          <div className="text-foreground-muted mb-2.5 flex flex-none text-[11px] tracking-[0.12em] uppercase">
            <span>Extracted text — already yours to read</span>
            <span className="ml-auto tabular-nums">
              {analysis.document.text.length.toLocaleString()} characters
            </span>
          </div>
          <div className="text-foreground/85 text-[clamp(14.5px,1.05vw,16px)] leading-[1.75] whitespace-pre-wrap lg:flex-1 lg:overflow-y-auto lg:pr-2">
            {analysis.document.text}
          </div>
        </section>

        <section
          aria-label="Findings so far"
          className="mt-9 block lg:mt-0 lg:flex lg:min-h-0 lg:flex-col"
        >
          <div className="text-foreground-muted mb-2.5 flex flex-none text-[11px] tracking-[0.12em] uppercase">
            <span>Landing as they are found</span>
            <span className="ml-auto tabular-nums">{findings.length} so far</span>
          </div>
          <div className="flex flex-col gap-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-2">
            {findings.length === 0 ? (
              <p className="text-foreground-muted max-w-[400px] text-sm leading-relaxed italic">
                Nothing flagged yet. Each clause is read on its own against a fixed rubric, so
                findings appear one at a time rather than all at the end.
              </p>
            ) : (
              findings.map((finding) => <Landed key={findingKey(finding)} finding={finding} />)
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Landed({ finding }: { finding: Finding }) {
  return (
    <article>
      <p
        className={cn(
          'text-[11px] tracking-[0.12em] uppercase tabular-nums',
          SEVERITY_INK[finding.severity],
        )}
      >
        {SEVERITY_LABEL[finding.severity]} — {categoryLabel(finding.category)}
        {finding.citation.page !== null && ` · page ${finding.citation.page}`}
      </p>
      <h2 className="mt-1 text-[19px] leading-tight font-semibold tracking-[-0.015em]">
        {finding.title}
      </h2>
      <p className="text-foreground/85 mt-1.5 text-sm leading-relaxed">{finding.reason}</p>
    </article>
  );
}

function pages(analysis: Analysis): string {
  const count = analysis.document.page_count;
  return count === null ? 'page count unknown' : `${count} ${count === 1 ? 'page' : 'pages'}`;
}

/** The step the user is on, named the way they would say it. */
function headline(analysis: Analysis): string {
  const { stage, clauses_done: done, clauses_total: total } = analysis;
  if (stage === 'extracting') return 'Reading the file';
  if (stage === 'segmenting') return 'Finding the clauses';
  if (stage === 'analyzing') {
    const current = Math.min(total, done + 1);
    return `Clause ${String(current).padStart(2, '0')} of ${total}`;
  }
  if (stage === 'judging') return 'Scoring severities again';
  return 'Finishing up';
}

/** Seconds since mount. The only thing on this screen the client owns. */
function useElapsed(): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return seconds;
}
