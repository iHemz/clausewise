'use client';

import { FileText, Loader2, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { cn } from '@/lib/utils';

const ACCEPTED = '.pdf,.docx';

interface Props {
  onAnalyze: (file: File) => void;
  isPending: boolean;
}

export function Uploader({ onAnalyze, isPending }: Props) {
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
    <div>
      <div
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
          'border-border rounded-xl border-2 border-dashed p-10 text-center transition-colors',
          isDragging && 'border-accent bg-accent/5',
        )}
      >
        {isPending ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="text-accent size-8 animate-spin" aria-hidden />
            <p className="font-medium">Reading the contract…</p>
            <p className="text-foreground-muted text-sm">
              Every clause is reviewed separately, then severities are scored a second time. A long
              agreement can take a minute or two.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <FileText className="text-foreground-muted size-8" aria-hidden />
            <p className="font-medium">Drop a contract here</p>
            <p className="text-foreground-muted text-sm">PDF or DOCX, up to 15MB</p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-2 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              <Upload className="size-4" aria-hidden />
              Choose a file
            </button>
          </div>
        )}

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

      {rejected && (
        <p role="alert" className="text-danger mt-3 text-sm">
          {rejected}
        </p>
      )}
    </div>
  );
}
