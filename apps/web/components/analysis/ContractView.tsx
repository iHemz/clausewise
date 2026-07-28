'use client';

import { useEffect, useRef } from 'react';
import type { Finding } from '@/lib/api';
import { buildSegments, dominantSeverity, findingAnchorId } from '@/lib/highlight';
import { SEVERITY_MARK } from '@/lib/severity';
import { cn } from '@/lib/utils';

/**
 * The contract, rendered with every cited span highlighted.
 *
 * This is the verification surface: a reviewer clicks a finding on the right
 * and lands on the exact words it came from. That round trip is what separates
 * a tool a lawyer can check from one they have to trust.
 */

interface Props {
  text: string;
  findings: Finding[];
  /** The finding currently selected in the list, scrolled into view. */
  selectedId: string | null;
  /**
   * Whether this pane owns a scrollbar. False on narrow screens, where the
   * page is the only scroller — a scroll box inside a page scroll is the thing
   * that makes a contract impossible to follow on a phone.
   */
  scrolls?: boolean;
  onSelect: (finding: Finding) => void;
}

export function ContractView({ text, findings, selectedId, scrolls = true, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const segments = buildSegments(text, findings);

  // Centre the selected citation in the pane when the selection changes.
  //
  // Set `scrollTop` rather than call `scrollIntoView`: this pane is one of two
  // independent scrollers inside a fixed-height shell, and scrollIntoView also
  // scrolls whatever ancestor it decides needs to move. Offsets are measured
  // from the rects, not `offsetTop`, so the maths does not depend on which
  // ancestor happens to be positioned.
  useEffect(() => {
    const pane = containerRef.current;
    if (!selectedId || !pane || !scrolls) return;
    const target = pane.querySelector<HTMLElement>(`[data-anchor="${selectedId}"]`);
    if (!target) return;
    const delta = target.getBoundingClientRect().top - pane.getBoundingClientRect().top;
    pane.scrollTop = Math.max(0, pane.scrollTop + delta - pane.clientHeight / 2.6);
  }, [selectedId, scrolls]);

  return (
    <div
      ref={containerRef}
      className={cn(
        'whitespace-pre-wrap',
        scrolls
          ? 'flex-1 overflow-y-auto pr-2.5 text-[clamp(14.5px,1.05vw,16px)] leading-[1.8]'
          : 'max-w-[40em] text-base leading-[1.8]',
      )}
    >
      {segments.map((segment) => {
        const severity = dominantSeverity(segment.findings);

        if (!severity || segment.findings.length === 0) {
          return <span key={segment.start}>{segment.text}</span>;
        }

        const primary = segment.findings[0]!;
        const anchor = findingAnchorId(primary);
        const isSelected = segment.findings.some((f) => findingAnchorId(f) === selectedId);

        return (
          <mark
            key={segment.start}
            data-anchor={anchor}
            onClick={() => onSelect(primary)}
            className={cn('mark', isSelected ? 'mark-selected' : SEVERITY_MARK[severity])}
            title={segment.findings.map((f) => f.title).join(' · ')}
          >
            {segment.text}
          </mark>
        );
      })}
    </div>
  );
}
