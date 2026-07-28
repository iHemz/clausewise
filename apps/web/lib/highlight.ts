import type { Finding, Severity } from '@/lib/api';

/**
 * Turn the contract text plus a set of citations into a flat list of segments
 * ready to render.
 *
 * Pure and framework-free on purpose: this is the logic that decides which
 * characters get highlighted, and getting it wrong means the UI points a
 * reviewer at the wrong words. That deserves tests, not a debugger.
 *
 * Citations can overlap — two findings on the same sentence is normal — so
 * boundaries are flattened and each resulting segment carries every finding
 * covering it. The highest severity present wins the colour.
 */

export interface TextSegment {
  text: string;
  start: number;
  /** Findings whose citation covers this segment. Empty for plain text. */
  findings: Finding[];
}

const SEVERITY_RANK: Record<Severity, number> = { high: 3, medium: 2, low: 1 };

/** The most serious severity among the findings covering a segment. */
export function dominantSeverity(findings: Finding[]): Severity | null {
  if (findings.length === 0) return null;
  return findings.reduce<Severity>(
    (worst, finding) =>
      SEVERITY_RANK[finding.severity] > SEVERITY_RANK[worst] ? finding.severity : worst,
    'low',
  );
}

export function buildSegments(text: string, findings: Finding[]): TextSegment[] {
  if (!text) return [];

  // Ignore citations that fall outside the text rather than throwing — a bad
  // span should cost one highlight, not the whole document view.
  const valid = findings.filter(
    (f) =>
      f.citation.start >= 0 && f.citation.end <= text.length && f.citation.start < f.citation.end,
  );

  if (valid.length === 0) {
    return [{ text, start: 0, findings: [] }];
  }

  // Every citation edge becomes a cut point, so overlapping spans produce
  // segments that are each covered by a consistent set of findings.
  const cuts = new Set<number>([0, text.length]);
  for (const finding of valid) {
    cuts.add(finding.citation.start);
    cuts.add(finding.citation.end);
  }

  const ordered = [...cuts].sort((a, b) => a - b);
  const segments: TextSegment[] = [];

  for (let i = 0; i < ordered.length - 1; i += 1) {
    const start = ordered[i]!;
    const end = ordered[i + 1]!;
    if (end <= start) continue;

    segments.push({
      text: text.slice(start, end),
      start,
      findings: valid.filter((f) => f.citation.start <= start && f.citation.end >= end),
    });
  }

  return segments;
}

/**
 * A stable DOM id for a *cited span*, so clicking a finding can scroll to it.
 *
 * Deliberately not unique per finding: two findings that quote the same words
 * share one highlight in the contract, which is the correct behaviour — there
 * is only one set of words to point at. Use {@link findingKey} for anything
 * that needs one value per finding.
 */
export function findingAnchorId(finding: Finding): string {
  return `finding-${finding.clause_id}-${finding.citation.start}`;
}

/**
 * A unique identity for one finding, for React list keys.
 *
 * Separate from {@link findingAnchorId} because they answer different
 * questions: the anchor identifies a span, this identifies a finding. Using the
 * anchor as a key looks right and is not — the model routinely flags two
 * different risks in the same sentence, and React then renders siblings with
 * duplicate keys, which it warns about and which makes list updates unreliable.
 * Observed live: dozens of duplicate-key errors while findings streamed in.
 */
export function findingKey(finding: Finding): string {
  const { clause_id: clause, category, title, citation } = finding;
  return `${clause}:${citation.start}-${citation.end}:${category}:${title}`;
}

export const CATEGORY_LABELS: Record<string, string> = {
  unlimited_liability: 'Unlimited liability',
  limitation_of_liability: 'Liability cap',
  auto_renewal: 'Auto-renewal',
  unilateral_termination: 'Unilateral termination',
  ip_assignment: 'IP assignment',
  non_compete: 'Non-compete',
  indemnity: 'Indemnity',
  governing_law: 'Governing law',
  payment_terms: 'Payment terms',
  confidentiality: 'Confidentiality',
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replace(/_/g, ' ');
}
