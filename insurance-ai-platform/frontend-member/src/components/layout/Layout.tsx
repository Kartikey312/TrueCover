import type { ReactNode } from "react";

import { Header } from "./Header";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}
