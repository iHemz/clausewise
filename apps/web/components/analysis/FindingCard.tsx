'use client';

import type { Finding } from '@/lib/api';
import { categoryLabel } from '@/lib/highlight';
import { SEVERITY_INK, SEVERITY_LABEL } from '@/lib/severity';
import { cn } from '@/lib/utils';

interface Props {
  finding: Finding;
  isSelected: boolean;
  onSelect: () => void;
  /** Narrow screens only: take the reader to the citation in the contract tab. */
  onJumpToCitation?: () => void;
}

/**
 * One finding, as an editorial entry rather than a card.
 *
 * No border and no fill: this system separates items with whitespace, so the
 * only rule on the page is the one that marks the selected entry. The whole
 * entry is the hit target, because its job is to take you to the source text.
 */
export function FindingCard({ finding, isSelected, onSelect, onJumpToCitation }: Props) {
  // Disagreement between the two passes is shown, not averaged away — the
  // reviewer should know when the second opinion differed.
  const disputed = finding.judge_severity !== null && finding.judge_severity !== finding.severity;

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={isSelected}
        className={cn(
          'focus-visible:outline-accent -ml-[17px] block w-full border-l pl-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2',
          isSelected ? 'border-accent' : 'hover:border-border border-transparent',
        )}
      >
        <div className="flex items-baseline gap-2.5">
          <span
            className={cn(
              'text-[11px] tracking-[0.12em] uppercase',
              SEVERITY_INK[finding.severity],
            )}
          >
            {SEVERITY_LABEL[finding.severity]} — {categoryLabel(finding.category)}
            {finding.citation.page !== null && ` · page ${finding.citation.page}`}
          </span>
          <span className="text-accent-faint ml-auto text-[11px] tracking-[0.12em] uppercase tabular-nums">
            {finding.clause_id}
          </span>
        </div>

        <h3 className="mt-1 text-[21px] leading-tight font-semibold tracking-[-0.015em]">
          {finding.title}
        </h3>

        <p className="mt-2 text-[14.5px] leading-relaxed">{finding.reason}</p>

        <blockquote className="border-accent text-foreground-muted mt-2.5 border-l pl-3.5 text-sm leading-relaxed italic">
          &ldquo;{finding.citation.quote}&rdquo;
        </blockquote>

        <p className="mt-2.5 text-[14.5px] leading-relaxed">
          <span className="text-accent-ink text-[11px] tracking-[0.12em] uppercase">Rewrite </span>
          {finding.suggested_rewrite}
        </p>

        {disputed && (
          <p className="text-accent-2-ink mt-2.5 text-[13.5px] leading-relaxed">
            The second reviewer scored this {finding.judge_severity}
            {finding.judge_note && ` — ${finding.judge_note}`}. Severity is shown as the higher of
            the two, not averaged.
          </p>
        )}
      </button>

      {onJumpToCitation && (
        <button
          type="button"
          onClick={onJumpToCitation}
          className="border-accent text-accent-ink focus-visible:outline-accent mt-3 min-h-11 rounded-md border px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Read it in the contract &rarr;
        </button>
      )}
    </li>
  );
}
