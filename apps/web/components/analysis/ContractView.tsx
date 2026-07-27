'use client';

import { useEffect, useRef } from 'react';
import type { Finding } from '@/lib/api';
import { buildSegments, dominantSeverity, findingAnchorId } from '@/lib/highlight';
import { cn } from '@/lib/utils';

/**
 * The contract, rendered with every cited span highlighted.
 *
 * This is the verification surface: a reviewer clicks a finding on the right
 * and lands on the exact words it came from. That round trip is what separates
 * a tool a lawyer can check from one they have to trust.
 */

const SEVERITY_MARK: Record<string, string> = {
  high: 'bg-danger/15 border-b-2 border-danger/60',
  medium: 'bg-warning/15 border-b-2 border-warning/60',
  low: 'bg-accent/10 border-b-2 border-accent/40',
};

interface Props {
  text: string;
  findings: Finding[];
  /** The finding currently selected in the list, scrolled into view. */
  selectedId: string | null;
  onSelect: (finding: Finding) => void;
}

export function ContractView({ text, findings, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const segments = buildSegments(text, findings);

  // Scroll the selected citation into view when the selection changes.
  useEffect(() => {
    if (!selectedId) return;
    const target = containerRef.current?.querySelector(`[data-anchor="${selectedId}"]`);
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [selectedId]);

  return (
    <div
      ref={containerRef}
      className="border-border bg-surface h-[70vh] overflow-y-auto rounded-xl border p-6 font-mono text-[13px] leading-relaxed whitespace-pre-wrap"
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
            className={cn(
              'cursor-pointer rounded-sm text-inherit transition-colors',
              SEVERITY_MARK[severity],
              isSelected && 'ring-accent bg-accent/25 ring-2',
            )}
            title={segment.findings.map((f) => f.title).join(' · ')}
          >
            {segment.text}
          </mark>
        );
      })}
    </div>
  );
}
