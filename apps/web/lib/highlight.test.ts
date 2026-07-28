import type { Finding, Severity } from '@/lib/api';
import {
  buildSegments,
  categoryLabel,
  dominantSeverity,
  findingAnchorId,
  findingKey,
} from './highlight';

const TEXT = 'The Supplier shall indemnify the Client without limitation.';

function finding(start: number, end: number, severity: Severity = 'high'): Finding {
  return {
    clause_id: 'c1',
    title: 'Uncapped indemnity',
    category: 'indemnity',
    severity,
    reason: 'No cap on liability.',
    suggested_rewrite: 'Cap the indemnity.',
    citation: { start, end, page: null, quote: TEXT.slice(start, end) },
    judge_severity: null,
    judge_note: null,
  };
}

describe('buildSegments', () => {
  it('returns nothing for empty text', () => {
    expect(buildSegments('', [])).toEqual([]);
  });

  it('returns one plain segment when there are no findings', () => {
    const segments = buildSegments(TEXT, []);
    expect(segments).toHaveLength(1);
    expect(segments[0]!.text).toBe(TEXT);
    expect(segments[0]!.findings).toEqual([]);
  });

  it('reassembles the original text exactly', () => {
    // The invariant that matters: highlighting must never drop or duplicate a
    // character of the contract.
    const segments = buildSegments(TEXT, [finding(19, 28), finding(40, 58)]);
    expect(segments.map((s) => s.text).join('')).toBe(TEXT);
  });

  it('marks only the cited span', () => {
    const segments = buildSegments(TEXT, [finding(40, 58)]);
    const marked = segments.filter((s) => s.findings.length > 0);
    expect(marked).toHaveLength(1);
    expect(marked[0]!.text).toBe('without limitation');
  });

  it('carries every finding that covers an overlapping segment', () => {
    // Two findings on the same sentence is normal; the overlap must belong to both.
    const segments = buildSegments(TEXT, [finding(19, 45), finding(40, 58)]);
    const overlap = segments.find((s) => s.findings.length === 2);
    expect(overlap).toBeDefined();
    expect(segments.map((s) => s.text).join('')).toBe(TEXT);
  });

  it('ignores citations that fall outside the text', () => {
    // A bad span should cost one highlight, not the whole document view.
    const segments = buildSegments(TEXT, [finding(0, 9999)]);
    expect(segments.map((s) => s.text).join('')).toBe(TEXT);
  });

  it('ignores zero-width citations', () => {
    const segments = buildSegments(TEXT, [finding(10, 10)]);
    expect(segments).toHaveLength(1);
    expect(segments[0]!.findings).toEqual([]);
  });
});

describe('dominantSeverity', () => {
  it('is null when nothing covers the segment', () => {
    expect(dominantSeverity([])).toBeNull();
  });

  it('picks the most serious severity present', () => {
    expect(dominantSeverity([finding(0, 5, 'low'), finding(0, 5, 'high')])).toBe('high');
    expect(dominantSeverity([finding(0, 5, 'low'), finding(0, 5, 'medium')])).toBe('medium');
  });
});

describe('findingAnchorId', () => {
  it('is stable for the same finding and distinct across spans', () => {
    expect(findingAnchorId(finding(40, 58))).toBe(findingAnchorId(finding(40, 58)));
    expect(findingAnchorId(finding(40, 58))).not.toBe(findingAnchorId(finding(19, 28)));
  });
});

describe('categoryLabel', () => {
  it('maps known categories to readable labels', () => {
    expect(categoryLabel('unlimited_liability')).toBe('Unlimited liability');
  });

  it('falls back gracefully on an unknown category', () => {
    expect(categoryLabel('some_new_thing')).toBe('some new thing');
  });
});

describe('findingKey', () => {
  // The bug this pins: the anchor was used as a React key, and the model
  // routinely flags two different risks in the same sentence — which produced
  // duplicate keys and a stream of React warnings while findings landed.
  const sameSpan = (title: string, category: Finding['category']): Finding => ({
    ...finding(40, 58),
    title,
    category,
  });

  it('is distinct for two findings quoting the same words', () => {
    const a = sameSpan('Uncapped indemnity', 'indemnity');
    const b = sameSpan('Liability is not capped', 'unlimited_liability');

    expect(findingAnchorId(a)).toBe(findingAnchorId(b));
    expect(findingKey(a)).not.toBe(findingKey(b));
  });

  it('is distinct when only the title differs', () => {
    const a = sameSpan('Uncapped indemnity', 'indemnity');
    const b = sameSpan('Indemnity has no ceiling', 'indemnity');

    expect(findingKey(a)).not.toBe(findingKey(b));
  });

  it('is stable for the same finding across renders', () => {
    expect(findingKey(finding(40, 58))).toBe(findingKey(finding(40, 58)));
  });

  it('still separates findings on different spans', () => {
    expect(findingKey(finding(0, 10))).not.toBe(findingKey(finding(40, 58)));
  });
});
