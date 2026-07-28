import { AnalysisView } from '@/components/analysis/AnalysisView';

/**
 * Server component: the app shell.
 *
 * The shell is a sheet — it stops growing at 1680px and centres, with an edge
 * on each side, so a 2560px monitor reads as paper on a desk rather than a
 * page that failed to fill. Below `lg` it is an ordinary scrolling page: the
 * fixed-height two-pane layout only makes sense where two panes fit.
 */
export default function HomePage() {
  return (
    <div className="bg-surface border-border mx-auto flex w-full max-w-[1300px] flex-col lg:h-full lg:overflow-hidden lg:border-x">
      <header className="border-border flex flex-none flex-wrap items-baseline gap-x-4 gap-y-3 border-b px-[clamp(18px,3vw,34px)] py-4">
        <span className="text-[21px] font-semibold tracking-[-0.02em]">Clausewise</span>
        <span className="text-accent-ink text-[11px] tracking-[0.12em] uppercase">
          Contract review
        </span>
      </header>

      {/* A landmark, not a wrapper. Without it the one page that matters has no
          `main` for a screen reader to skip to, while `error.tsx` and
          `not-found.tsx` both have one. It carries the flex sizing the view
          used to get directly from the shell, so the layout is unchanged —
          `display: contents` would preserve it more literally but has a history
          of dropping the element from the accessibility tree, which is the one
          thing this is here for. */}
      <main className="flex min-h-0 flex-1 flex-col">
        <AnalysisView />
      </main>
    </div>
  );
}
