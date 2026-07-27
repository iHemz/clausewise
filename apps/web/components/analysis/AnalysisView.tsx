'use client';

import { useState } from 'react';
import { useAnalyzeContract } from '@/lib/queries/analyses';
import type { Finding } from '@/lib/api';
import { findingAnchorId } from '@/lib/highlight';
import { ContractView } from './ContractView';
import { FindingCard } from './FindingCard';
import { SeveritySummary } from './SeveritySummary';
import { Uploader } from './Uploader';

/**
 * The assembly point: owns the selection state and wires the uploader, the
 * contract pane, and the findings list together.
 */
export function AnalysisView() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const analyze = useAnalyzeContract();
  const analysis = analyze.data;

  function select(finding: Finding) {
    setSelectedId(findingAnchorId(finding));
  }

  if (!analysis) {
    return (
      <div className="mx-auto max-w-2xl">
        <Uploader
          onAnalyze={(file) => {
            setSelectedId(null);
            analyze.mutate(file);
          }}
          isPending={analyze.isPending}
        />
        {analyze.isError && (
          <p role="alert" className="text-danger mt-4 text-sm">
            {analyze.error.message}
          </p>
        )}
      </div>
    );
  }

  return (
    <div>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-medium">{analysis.document.filename}</h2>
          <p className="text-foreground-muted text-sm">
            {analysis.document.clauses.length} clauses · {analysis.findings.length} findings
            {analysis.dropped_ungrounded > 0 && (
              <>
                {' · '}
                <span title="The model described these but could not quote them, so they were discarded rather than shown with an approximate source.">
                  {analysis.dropped_ungrounded} dropped as ungrounded
                </span>
              </>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            analyze.reset();
            setSelectedId(null);
          }}
          className="border-border hover:bg-surface-muted focus-visible:outline-accent rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Analyze another
        </button>
      </header>

      {analysis.clauses_failed > 0 && (
        <p
          role="alert"
          className="border-warning/40 bg-warning/10 text-warning mb-4 rounded-xl border p-3 text-sm"
        >
          {analysis.clauses_failed} of {analysis.document.clauses.length} clauses could not be
          analyzed, so this document was only partly reviewed. Treat the findings below as
          incomplete rather than as a clean result.
        </p>
      )}

      <SeveritySummary findings={analysis.findings} />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section aria-label="Contract text">
          <ContractView
            text={analysis.document.text}
            findings={analysis.findings}
            selectedId={selectedId}
            onSelect={select}
          />
        </section>

        <section aria-label="Findings">
          {analysis.findings.length === 0 ? (
            <div className="border-border rounded-xl border p-6">
              <p className="font-medium">No risks flagged</p>
              <p className="text-foreground-muted mt-1 text-sm">
                Nothing in this document matched the risk rubric. That is a real answer, not a
                failure — but it is not a substitute for a lawyer reading it.
              </p>
            </div>
          ) : (
            <ul className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
              {analysis.findings.map((finding) => {
                const anchor = findingAnchorId(finding);
                return (
                  <FindingCard
                    key={anchor}
                    finding={finding}
                    isSelected={anchor === selectedId}
                    onSelect={() => setSelectedId(anchor)}
                  />
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
