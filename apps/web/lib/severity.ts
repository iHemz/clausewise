import type { Finding, Severity } from '@/lib/api';

/**
 * Severity as a presentation role, in one place.
 *
 * Three components need the same ink for the same severity — the summary
 * counts, the finding card and the citation highlight — and the fastest way to
 * make a design drift is to let each of them pick its own.
 */

export const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low'];

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

/** Text ink for a severity. */
export const SEVERITY_INK: Record<Severity, string> = {
  high: 'text-high',
  medium: 'text-medium',
  low: 'text-low',
};

/** Highlight treatment for a cited span — see `.mark-*` in globals.css. */
export const SEVERITY_MARK: Record<Severity, string> = {
  high: 'mark-high',
  medium: 'mark-medium',
  low: 'mark-low',
};

export function severityCounts(findings: Finding[]): Record<Severity, number> {
  return {
    high: findings.filter((f) => f.severity === 'high').length,
    medium: findings.filter((f) => f.severity === 'medium').length,
    low: findings.filter((f) => f.severity === 'low').length,
  };
}

/**
 * The one sentence at the top of a completed review.
 *
 * A count of findings is not a verdict — the reader wants to know whether to
 * worry before they read anything. High severity is the only thing that earns
 * an alarming headline, so nothing else gets one.
 */
export function verdictLine(findings: Finding[]): string {
  const counts = severityCounts(findings);

  if (counts.high === 1) return 'One clause puts real money at risk';
  if (counts.high > 1) return `${spell(counts.high)} clauses put real money at risk`;
  if (counts.medium > 0) {
    return counts.medium === 1
      ? 'One clause is worth negotiating'
      : `${spell(counts.medium)} clauses are worth negotiating`;
  }
  if (counts.low > 0) return 'Nothing serious, a few things worth knowing';
  return 'Nothing in this document matched the risk rubric';
}

const WORDS = [
  'Zero',
  'One',
  'Two',
  'Three',
  'Four',
  'Five',
  'Six',
  'Seven',
  'Eight',
  'Nine',
  'Ten',
];

/** Small numbers read better spelled out in a headline; figures stay tabular. */
function spell(n: number): string {
  return WORDS[n] ?? String(n);
}
