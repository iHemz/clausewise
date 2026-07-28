import type { Metadata } from 'next';
import { Source_Serif_4 } from 'next/font/google';
import { QueryProvider } from '@/components/providers/QueryProvider';
import './globals.css';

// One face for everything, italic included: in this system the serif is the
// interface chrome as well as the document, so there is no second family to
// load and nothing to fall back to a synthesized oblique.
const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  weight: ['400', '600'],
  style: ['normal', 'italic'],
  variable: '--font-source-serif',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Clausewise — contract clause risk analysis',
  description:
    'Upload a contract, get every risky clause flagged with a severity, a reason, a suggested rewrite, and a citation pointing at the exact source text.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`h-full ${sourceSerif.variable}`}>
      <body className="h-full antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
