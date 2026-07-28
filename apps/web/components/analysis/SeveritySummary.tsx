import type { Analysis, Finding } from '@/lib/api';
import { SEVERITY_INK, SEVERITY_LABEL, SEVERITY_ORDER, severityCounts } from '@/lib/severity';
import { cn } from '@/lib/utils';

/**
 * Counts, then the honesty line.
 *
 * Figures set tabular and unboxed — this system organises with whitespace, so
 * three counts in a row need no cards. The citation and provider line sits in
 * the same rank as the counts rather than in a footnote: how much of the
 * document was actually reviewed is part of the result, not a caveat about it.
 */
export function SeveritySummary({
  findings,
  analysis,
}: {
  findings: Finding[];
  analysis: Analysis;
}) {
  const counts = severityCounts(findings);
  const cited = findings.length;
  const providers = analysis.providers_used.join(', ');

  return (
    <div className="mt-4 flex flex-wrap items-baseline gap-x-8 gap-y-3">
      <div className="flex items-baseline gap-6">
        {SEVERITY_ORDER.map((severity) => (
          <p key={severity} className="flex items-baseline gap-2">
            <span
              className={cn(
                'text-[30px] leading-none font-semibold tracking-[-0.02em] tabular-nums',
                SEVERITY_INK[severity],
              )}
            >
              {counts[severity]}
            </span>
            <span className="text-foreground-muted text-[11px] tracking-[0.12em] uppercase">
              {SEVERITY_LABEL[severity]}
            </span>
          </p>
        ))}
      </div>

      <div className="bg-border h-4 w-px" aria-hidden />

      <p className="text-foreground-muted text-[13.5px] tabular-nums">
        {cited} of {cited} findings carry a citation
        {analysis.dropped_ungrounded > 0 ? (
          <span title="The model described these but could not quote them, so they were discarded rather than shown with an approximate source.">
            {' · '}
            {analysis.dropped_ungrounded} dropped as ungrounded
          </span>
        ) : (
          ' · 0 dropped as ungrounded'
        )}
      </p>

      {providers && (
        <p className="text-foreground-muted text-[13.5px] tabular-nums">
          Reviewed by {providers} · {analysis.clauses_total - analysis.clauses_failed} of{' '}
          {analysis.clauses_total} clauses analysed
        </p>
      )}
    </div>
  );
}
