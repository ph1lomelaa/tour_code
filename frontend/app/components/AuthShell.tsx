import type { ReactNode } from "react";
import { KaabaArt } from "./KaabaArt";

/** Общая рамка для страниц входа и приглашения. */
export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-brand-cream">
      {/* Слева — иллюстрация с Каабой */}
      <div className="relative hidden lg:flex w-[48%] flex-col justify-between overflow-hidden bg-brand-ink p-12">
        <KaabaArt className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 bg-gradient-to-b from-brand-ink/40 via-transparent to-brand-ink/60" />

        <div className="relative">
          <div className="mb-10">
            <p className="font-serif text-2xl tracking-[0.2em] text-white">HICKMET</p>
            <p className="text-xs tracking-[0.3em] text-brand-gold-light">PREMIUM</p>
          </div>
          <div className="mb-5 h-px w-16 bg-brand-gold-light" />
          <h2 className="font-serif text-4xl leading-tight text-white">Система управления<br />тур-кодами</h2>
          <p className="mt-3 max-w-sm text-sm text-white/80">
            Тур-коды, пакеты и паломники — в одном месте.
          </p>
        </div>

        <div className="relative flex items-end justify-between text-xs text-white/75">
          <p>Доступ только для сотрудников по приглашению</p>
          <p>© 2026 Hickmet Premium</p>
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        {/* Сверху — название системы */}
        <div className="flex items-center justify-between border-b border-brand-line px-6 py-5 md:px-10">
          <div className="lg:hidden">
            <p className="font-serif text-lg tracking-[0.2em] text-brand-ink">HICKMET</p>
            <p className="text-[10px] tracking-[0.3em] text-brand-gold">PREMIUM</p>
            <p className="mt-2 font-serif text-base text-brand-ink md:hidden">Система управления тур-кодами</p>
          </div>
          <p className="ml-auto hidden font-serif text-lg text-brand-ink md:block">Система управления тур-кодами</p>
        </div>

        <div className="flex flex-1 items-center justify-center px-4 py-10">
          <div className="w-full max-w-md">
            <div className="rounded-2xl border border-brand-line bg-white p-8 shadow-lg">
              <h1 className="mb-1 text-3xl text-brand-ink">{title}</h1>
              {subtitle && <p className="mb-6 text-sm text-brand-text">{subtitle}</p>}
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export const AUTH_INPUT = "h-11 bg-brand-card border-brand-line focus-visible:border-brand-accent";
export const AUTH_BUTTON = "h-11 w-full bg-brand-accent text-white hover:bg-brand-accent-hover";
