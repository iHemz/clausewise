import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link
        href="/"
        className="text-accent focus-visible:outline-accent mt-4 inline-block text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        Back home
      </Link>
    </main>
  );
}
