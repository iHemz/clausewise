import { AnalysisView } from '@/components/analysis/AnalysisView';

/** Server component: composes the page and hands interactivity to the view. */
export default function HomePage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Clausewise</h1>
        <p className="text-foreground-muted mt-2 max-w-2xl text-sm">
          Upload a contract and get every risky clause flagged with a severity, a plain-English
          reason, a suggested rewrite, and a citation pointing at the exact text it came from. Click
          any finding to jump to its source.
        </p>
      </header>

      <AnalysisView />

      <footer className="border-border text-foreground-muted mt-12 border-t pt-6 text-xs">
        Clausewise is a demonstration of grounded document AI. It is not legal advice, and every
        finding should be checked against the source text — which is exactly what the citations are
        for.
      </footer>
    </main>
  );
}
