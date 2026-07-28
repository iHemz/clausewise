import { AnalysisView } from '@/components/analysis/AnalysisView';

/**
 * Server component: the app shell. One full-height column — the header is
 * fixed and each state owns the space below it, so the contract and findings
 * panes scroll independently instead of the whole page moving.
 */
export default function HomePage() {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="border-border flex flex-none items-baseline gap-4 border-b px-8 py-4">
        <span className="text-[21px] font-semibold tracking-[-0.02em]">Clausewise</span>
        <span className="text-accent-ink text-[11px] tracking-[0.12em] uppercase">
          Contract review
        </span>
      </header>

      <AnalysisView />
    </div>
  );
}
