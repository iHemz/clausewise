'use client';

import { AlertTriangle, Scale } from 'lucide-react';
import type { Finding, Severity } from '@/lib/api';
import { categoryLabel } from '@/lib/highlight';
import { cn } from '@/lib/utils';

const SEVERITY_BADGE: Record<Severity, string> = {
  high: 'bg-danger/15 text-danger',
  medium: 'bg-warning/15 text-warning',
  low: 'bg-accent/10 text-accent',
};

interface Props {
  finding: Finding;
  isSelected: boolean;
  onSelect: () => void;
}

export function FindingCard({ finding, isSelected, onSelect }: Props) {
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
          'border-border hover:border-accent/60 focus-visible:outline-accent w-full rounded-xl border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2',
          isSelected && 'border-accent bg-accent/5',
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-medium">{finding.title}</h3>
          <span
            className={cn(
              'shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold uppercase',
              SEVERITY_BADGE[finding.severity],
            )}
          >
            {finding.severity}
          </span>
        </div>

        <p className="text-foreground-muted mt-1 text-xs">
          {categoryLabel(finding.category)}
          {finding.citation.page !== null && ` · page ${finding.citation.page}`}
        </p>

        <p className="mt-3 text-sm">{finding.reason}</p>

        <blockquote className="border-border text-foreground-muted mt-3 border-l-2 pl-3 font-mono text-xs">
          &ldquo;{finding.citation.quote}&rdquo;
        </blockquote>

        <div className="mt-3 flex items-start gap-2 text-sm">
          <Scale className="text-accent mt-0.5 size-4 shrink-0" aria-hidden />
          <p>
            <span className="text-foreground-muted">Suggested: </span>
            {finding.suggested_rewrite}
          </p>
        </div>

        {disputed && (
          <div className="text-warning mt-3 flex items-start gap-2 text-xs">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <p>
              Second reviewer scored this <strong>{finding.judge_severity}</strong>
              {finding.judge_note && ` — ${finding.judge_note}`}
            </p>
          </div>
        )}
      </button>
    </li>
  );
}
