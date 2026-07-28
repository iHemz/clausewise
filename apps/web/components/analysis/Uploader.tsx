'use client';

import { useRef, useState } from 'react';
import { cn } from '@/lib/utils';

const ACCEPTED = '.pdf,.docx';

/**
 * What happens after the upload, said before it.
 *
 * Most of the anxiety in this product is the wait, and most of that is not
 * knowing what the wait is for. Naming the four steps up front costs one column
 * and means the progress screen confirms an expectation instead of setting one.
 */
const STAGES = [
  {
    num: '01',
    label: 'Text extracted',
    detail: 'Characters read, page boundaries and offsets preserved',
  },
  {
    num: '02',
    label: 'Clauses segmented',
    detail: 'Split by numbering, then headings, with spans preserved',
  },
  {
    num: '03',
    label: 'Risk pass',
    detail: 'Every clause read on its own against a fixed risk rubric',
  },
  {
    num: '04',
    label: 'Second opinion',
    detail: 'An independent pass re-scores every severity',
  },
];

interface Props {
  onAnalyze: (file: File) => void;
  /** Shown under the drop zone — the API rejected the last attempt. */
  error?: string | null;
}

export function Uploader({ onAnalyze, error }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    // Check client-side too, so an obvious mistake fails instantly instead of
    // after a round trip. The server still validates — this is UX, not security.
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setRejected(`${file.name} is not a PDF or DOCX.`);
      return;
    }
    setRejected(null);
    onAnalyze(file);
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-16 overflow-y-auto px-8 py-12 lg:grid-cols-[1.25fr_1fr]">
      <div className="max-w-[620px]">
        <p className="text-foreground-muted text-[11px] tracking-[0.12em] uppercase">
          Upload a contract
        </p>
        <h1 className="mt-3 text-[52px] leading-[1.05] font-semibold tracking-[-0.025em] text-pretty">
          Every risky clause, flagged and quoted from the source.
        </h1>
        <p className="mt-5 max-w-[540px] text-[17px] leading-relaxed">
          Each finding carries a citation into the exact words it came from. If the model cannot
          quote what it is flagging, the finding is dropped rather than shown with an approximate
          source — and you are told how many were dropped.
        </p>

        {/* The whole zone opens the picker, not just the button inside it — a
            dashed target that says "drop a contract here" reads as clickable,
            and a pointer cursor over something inert is a small lie of its own.
            No `role="button"` on purpose: the real button below is the
            keyboard-accessible control, and nesting one interactive element
            inside another confuses screen readers. This is a mouse affordance
            layered on top of an already-accessible one. */}
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFile(event.dataTransfer.files[0]);
          }}
          className={cn(
            'mt-8 cursor-pointer rounded-md border border-dashed p-10 transition-colors',
            isDragging
              ? 'border-accent bg-accent/5'
              : 'border-foreground/30 hover:border-foreground/50',
          )}
        >
          <p className="text-2xl font-semibold tracking-[-0.015em]">Drop a contract here</p>
          <p className="text-foreground-muted mt-1.5 text-sm tabular-nums">
            PDF or DOCX · up to 15 MB · nothing is stored after the review
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-5">
            <button
              type="button"
              onClick={(event) => {
                // The zone around this button opens the picker too; without
                // this the click bubbles and asks for it twice.
                event.stopPropagation();
                inputRef.current?.click();
              }}
              className="bg-accent hover:bg-accent-hover focus-visible:outline-accent rounded-md px-5 py-2.5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Choose a file
            </button>
            <span className="text-foreground-muted text-[13px]">
              PDF or DOCX, straight from your inbox
            </span>
          </div>
        </div>

        {rejected && (
          <p role="alert" className="text-danger mt-3 text-sm">
            {rejected}
          </p>
        )}
        {error && (
          <p role="alert" className="text-danger mt-3 text-sm">
            {error}
          </p>
        )}

        <p className="text-foreground-muted mt-6 max-w-[540px] text-[13.5px] leading-relaxed italic">
          Clausewise is not legal advice. Every finding is built to be checked against the source
          text — which is exactly what the citations are for.
        </p>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="sr-only"
          aria-label="Upload a contract"
          onChange={(event) => {
            handleFile(event.target.files?.[0]);
            // Reset so re-selecting the same file fires `change` again.
            event.target.value = '';
          }}
        />
      </div>

      <div className="max-w-[400px] pt-9">
        <p className="text-foreground-muted text-[11px] tracking-[0.12em] uppercase">
          What happens after you upload
        </p>
        <ol className="mt-4 flex flex-col gap-5">
          {STAGES.map((stage) => (
            <li key={stage.num} className="grid grid-cols-[34px_1fr] items-baseline gap-3">
              <span className="text-accent-faint text-[19px] font-semibold tabular-nums">
                {stage.num}
              </span>
              <span>
                <span className="block text-[17px] font-semibold tracking-[-0.01em]">
                  {stage.label}
                </span>
                <span className="text-foreground-muted mt-0.5 block text-[13.5px] leading-relaxed">
                  {stage.detail}
                </span>
              </span>
            </li>
          ))}
        </ol>
        <p className="border-border text-foreground-muted mt-7 border-t pt-3.5 text-[13.5px] leading-relaxed">
          A two-page agreement takes about thirty seconds. Findings appear as they are found — the
          review is not hidden until the end.
        </p>
      </div>
    </div>
  );
}
