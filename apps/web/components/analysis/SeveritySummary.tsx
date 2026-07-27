import type { Finding, Severity } from '@/lib/api';
import { cn } from '@/lib/utils';

const LEVELS: { severity: Severity; label: string; className: string }[] = [
  { severity: 'high', label: 'High', className: 'bg-danger/10 text-danger' },
  { severity: 'medium', label: 'Medium', className: 'bg-warning/10 text-warning' },
  { severity: 'low', label: 'Low', className: 'bg-accent/10 text-accent' },
];

/** A count per severity. Presentational, so it stays a server component. */
export function SeveritySummary({ findings }: { findings: Finding[] }) {
  return (
    <div className="flex flex-wrap gap-3">
      {LEVELS.map(({ severity, label, className }) => (
        <div key={severity} className={cn('rounded-xl px-4 py-3', className)}>
          <p className="text-2xl font-semibold tabular-nums">
            {findings.filter((f) => f.severity === severity).length}
          </p>
          <p className="text-xs font-medium uppercase">{label}</p>
        </div>
      ))}
    </div>
  );
}
