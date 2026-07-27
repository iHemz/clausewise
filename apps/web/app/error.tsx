'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6">
      <h1 className="text-danger text-xl font-semibold">Something went wrong</h1>
      <p className="text-foreground-muted mt-2 text-sm">{error.message}</p>
      <button
        onClick={reset}
        className="bg-accent hover:bg-accent-hover focus-visible:outline-accent mt-6 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        Try again
      </button>
    </main>
  );
}
