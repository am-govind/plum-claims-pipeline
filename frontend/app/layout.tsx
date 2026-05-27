import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plum Claims Pipeline",
  description: "Multi-agent health insurance claims processing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-50 text-ink-900 antialiased">
        <header className="border-b border-ink-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-ink-900 text-center font-bold leading-8 text-white">
                P
              </div>
              <div className="font-semibold tracking-tight">
                Plum Claims Pipeline
              </div>
            </Link>
            <nav className="flex gap-6 text-sm font-medium text-ink-600">
              <Link href="/submit" className="hover:text-ink-900">
                Submit a claim
              </Link>
              <Link href="/eval" className="hover:text-ink-900">
                Eval suite
              </Link>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="hover:text-ink-900"
              >
                API docs
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
        <footer className="border-t border-ink-200 bg-white py-6 text-center text-xs text-ink-500">
          Multi-agent claims processing — built for the Plum AI Engineer assignment
        </footer>
      </body>
    </html>
  );
}
