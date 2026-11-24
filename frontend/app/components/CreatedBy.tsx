/** «24.11.2026 14:32 · Айша» — когда и кем получен тур-код. Время в часовом поясе браузера. */
export function CreatedBy({ at, by }: { at?: string; by?: string }) {
  if (!at && !by) return <span className="text-brand-muted">—</span>;
  const date = at ? new Date(at) : null;
  const when =
    date && !Number.isNaN(date.getTime())
      ? date.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
      : "";
  return (
    <div className="whitespace-nowrap leading-tight">
      {when && <div className="text-xs text-brand-text">{when}</div>}
      {by && <div className="text-xs text-brand-muted">{by}</div>}
    </div>
  );
}
