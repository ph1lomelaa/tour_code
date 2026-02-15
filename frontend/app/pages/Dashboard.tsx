import { Link, useNavigate } from "react-router";
import {
  Package,
  Users,
  Plus,
  Plane,
  CheckCircle2,
  ArrowRight,
  Send,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  getDashboardStats,
  getDashboardRecent,
  DashboardStatsResponse,
  RecentTourItem,
  RecentJobItem,
} from "../../src/lib/api/dashboard";

const STATUS_CONFIG: Record<string, { label: string; dot: string }> = {
  sent:    { label: "Отправлено", dot: "bg-emerald-400" },
  queued:  { label: "В очереди",  dot: "bg-amber-400" },
  sending: { label: "Отправка",   dot: "bg-sky-400" },
  failed:  { label: "Ошибка",     dot: "bg-red-400" },
  draft:   { label: "Черновик",    dot: "bg-stone-300" },
};

function StatusDot({ status }: { status: string | null }) {
  if (!status) return null;
  const cfg = STATUS_CONFIG[status] || { label: status, dot: "bg-stone-300" };
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] tracking-wide text-[#8B6F47]">
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStatsResponse>({
    total_tours: 0,
    total_pilgrims: 0,
    sent_jobs: 0,
    queued_jobs: 0,
    failed_jobs: 0,
  });
  const [recentTours, setRecentTours] = useState<RecentTourItem[]>([]);
  const [recentJobs, setRecentJobs] = useState<RecentJobItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const [statsData, recentData] = await Promise.all([
          getDashboardStats(),
          getDashboardRecent(),
        ]);
        if (cancelled) return;
        setStats(statsData);
        setRecentTours(recentData.recent_tours);
        setRecentJobs(recentData.recent_jobs);
      } catch (error) {
        console.error("Error loading dashboard:", error);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const handleSearch = (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/pilgrims?search=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      navigate("/pilgrims");
    }
  };

  return (
    <div className="relative min-h-full bg-[#E8E0D4]">
      {/* ── Decorative background ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-[#C4A265]/[0.1] blur-[100px]" />
        <div className="absolute top-[40%] -left-60 w-[500px] h-[500px] rounded-full bg-[#B8985F]/[0.08] blur-[120px]" />
        <div className="absolute -bottom-32 left-1/3 w-[400px] h-[400px] rounded-full bg-[#D4C5B0]/[0.09] blur-[100px]" />
      </div>

      <div className="relative px-6 py-10 md:px-14 md:py-14">
        <div className="max-w-[1100px] mx-auto">

          {/* ── Header ── */}
          <header className="mb-8">
            <h1 className="text-3xl md:text-[38px] leading-tight text-[#8B6F47] mb-2" dir="rtl">
              السلام عليكم ورحمة الله وبركاته
            </h1>
            <p className="text-[14px] text-[#6B5435]">
              Система управления тур кодами Hickmet Premium
            </p>
          </header>

          {/* ── Search bar ── */}
          <form onSubmit={handleSearch} className="mb-10">
            <div className="
              relative rounded-2xl
              backdrop-blur-2xl bg-white/[0.55]
              border border-white/70
              shadow-[0_4px_20px_rgba(139,111,71,0.08)]
              overflow-hidden
            ">
              <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-[#B8985F]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск паломника по имени, паспорту или телефону..."
                className="w-full bg-transparent pl-14 pr-5 py-4 text-[14px] text-[#2B2318] placeholder-[#B8985F]/60 outline-none"
              />
            </div>
          </form>

          {/* ── Stats ── */}
          <div className="grid grid-cols-3 gap-3 md:gap-5 mb-10">
            <GlassStat
              value={stats.total_tours}
              label="Всего туров"
              hint="Создано в системе"
              icon={<Plane className="w-5 h-5" />}
              isLoading={isLoading}
            />
            <GlassStat
              value={stats.total_pilgrims}
              label="Активных паломников"
              hint="С валидным паспортом"
              icon={<Users className="w-5 h-5" />}
              isLoading={isLoading}
            />
            <GlassStat
              value={stats.sent_jobs}
              label="Успешных отправок"
              hint="Завершены без ошибок"
              icon={<CheckCircle2 className="w-5 h-5" />}
              isLoading={isLoading}
            />
          </div>

          {/* ── Quick actions ── */}
          <div className="mb-10">
            <h2 className="text-[13px] tracking-[0.15em] uppercase text-[#8B6F47] mb-5">
              Быстрые действия
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5">
              <ActionCard
                to="/create"
                icon={<Plus className="w-6 h-6" />}
                title="Создать тур код"
                subtitle="Создать новый тур код для паломников на Умру или Хадж"
              />
              <ActionCard
                to="/packages"
                icon={<Package className="w-6 h-6" />}
                title="Пакеты с тур кодом"
                subtitle="Просмотр и управление пакетами"
              />
              <ActionCard
                to="/pilgrims"
                icon={<Users className="w-6 h-6" />}
                title="Паломники"
                subtitle="Управление списком паломников"
              />
            </div>
          </div>

          {/* ── Recent Tours Table ── */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-[13px] tracking-[0.15em] uppercase text-[#8B6F47]">
                Ближайшие туры
              </h2>
              <Link
                to="/packages"
                className="text-[12px] text-[#B8985F] hover:text-[#8B6F47] flex items-center gap-1 transition-colors"
              >
                Все туры <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <GlassPanel>
              {isLoading ? (
                <SkeletonTable />
              ) : recentTours.length === 0 ? (
                <EmptyState
                  icon={<Plane className="w-8 h-8" />}
                  text=""
                  linkTo="/create"
                  linkLabel="Создать первый тур"
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[#E5DDD0]/60">
                        <th className="text-left text-[11px] tracking-[0.1em] uppercase text-[#9C8B75] pb-3 font-medium">Направление</th>
                        <th className="text-left text-[11px] tracking-[0.1em] uppercase text-[#9C8B75] pb-3 font-medium">Даты</th>
                        <th className="text-left text-[11px] tracking-[0.1em] uppercase text-[#9C8B75] pb-3 font-medium">Паломники</th>
                        <th className="text-left text-[11px] tracking-[0.1em] uppercase text-[#9C8B75] pb-3 font-medium">Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentTours.map((tour) => (
                        <tr key={tour.id} className="border-b border-[#E5DDD0]/30 last:border-0">
                          <td className="py-3.5">
                            <Link to={`/create?tourId=${tour.id}`} className="text-[13px] text-[#2B2318] hover:text-[#B8985F] transition-colors">
                              {tour.sheet_name || tour.route || "Тур"}
                            </Link>
                          </td>
                          <td className="py-3.5 text-[13px] text-[#6B5435]">
                            {tour.date_start} — {tour.date_end}
                          </td>
                          <td className="py-3.5 text-[13px] text-[#6B5435]">
                            {tour.pilgrims_count}
                          </td>
                          <td className="py-3.5">
                            <StatusDot status={tour.dispatch_status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </GlassPanel>
          </div>

          {/* ── Recent Jobs ── */}
          {recentJobs.length > 0 && !isLoading && (
            <div>
              <h2 className="text-[13px] tracking-[0.15em] uppercase text-[#8B6F47] mb-5">
                Последние отправки
              </h2>
              <GlassPanel>
                <ul className="space-y-1">
                  {recentJobs.map((job) => (
                    <li
                      key={job.id}
                      className="flex items-center gap-3.5 px-3.5 py-3 -mx-1 rounded-xl"
                    >
                      <div className={`w-9 h-9 rounded-[10px] flex items-center justify-center flex-shrink-0 ${
                        job.status === "sent"
                          ? "bg-emerald-50"
                          : job.status === "failed"
                            ? "bg-red-50"
                            : "bg-amber-50"
                      }`}>
                        {job.status === "sent" ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        ) : job.status === "failed" ? (
                          <span className="w-4 h-4 rounded-full border-2 border-red-300 flex items-center justify-center text-[9px] text-red-400 font-bold">!</span>
                        ) : (
                          <Send className="w-3.5 h-3.5 text-amber-500" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] text-[#2B2318] truncate leading-tight">
                          {job.tour_sheet_name || `#${job.id.slice(0, 8)}`}
                        </p>
                        <p className="text-[11px] text-[#A99B88] mt-0.5">
                          {new Date(job.created_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" })}
                          {job.status === "failed" && job.error_message && (
                            <span className="text-red-300 ml-1">
                              — {job.error_message.slice(0, 35)}
                              {job.error_message.length > 35 ? "..." : ""}
                            </span>
                          )}
                        </p>
                      </div>
                      <StatusDot status={job.status} />
                    </li>
                  ))}
                </ul>
              </GlassPanel>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Sub-components
   ───────────────────────────────────────────── */

function GlassStat({
  value,
  label,
  hint,
  icon,
  isLoading,
}: {
  value: number;
  label: string;
  hint: string;
  icon: React.ReactNode;
  isLoading: boolean;
}) {
  return (
    <div className="
      relative overflow-hidden rounded-2xl
      backdrop-blur-2xl bg-white/[0.55]
      border border-white/70
      shadow-[0_4px_20px_rgba(139,111,71,0.08),0_1px_3px_rgba(139,111,71,0.04)]
      px-5 py-5 md:px-6 md:py-5
      transition-all duration-300 hover:bg-white/70 hover:shadow-[0_6px_24px_rgba(139,111,71,0.12)]
    ">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] tracking-[0.1em] uppercase text-[#9C8B75] mb-2">{label}</p>
          <p className="text-[28px] md:text-[32px] leading-none text-[#2B2318] tracking-tight font-medium">
            {isLoading ? (
              <span className="inline-block w-10 h-8 rounded-lg bg-[#E5DDD0]/40 animate-pulse" />
            ) : (
              value
            )}
          </p>
          <p className="text-[12px] text-[#B8985F]/70 mt-2">{hint}</p>
        </div>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#C4A265]/15 to-[#B8985F]/5 flex items-center justify-center text-[#C4A265]">
          {icon}
        </div>
      </div>
    </div>
  );
}

function ActionCard({
  to,
  icon,
  title,
  subtitle,
}: {
  to: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <Link
      to={to}
      className="
        group relative overflow-hidden rounded-2xl
        backdrop-blur-2xl bg-white/[0.55]
        border border-white/70
        shadow-[0_6px_24px_rgba(139,111,71,0.08),0_2px_6px_rgba(139,111,71,0.04)]
        px-6 py-7 md:px-7 md:py-8
        transition-all duration-300
        hover:bg-white/70 hover:shadow-[0_10px_36px_rgba(139,111,71,0.14)] hover:-translate-y-px
      "
    >
      {/* Hover copper glow */}
      <div className="absolute -bottom-10 -right-10 w-32 h-32 rounded-full bg-gradient-to-br from-[#C4A265] to-[#B8985F] opacity-0 group-hover:opacity-[0.08] blur-2xl transition-opacity duration-500" />

      <div className="relative">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#C4A265] to-[#A88952] text-white flex items-center justify-center mb-5 shadow-[0_4px_16px_rgba(139,111,71,0.25)] group-hover:shadow-[0_6px_24px_rgba(139,111,71,0.35)] group-hover:scale-[1.03] transition-all duration-300">
          {icon}
        </div>
        <h3 className="text-[15px] font-medium text-[#2B2318] leading-tight mb-1.5 group-hover:text-[#8B6F47] transition-colors">
          {title}
        </h3>
        <p className="text-[13px] text-[#9C8B75] leading-snug">{subtitle}</p>
      </div>
    </Link>
  );
}

function GlassPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="
      rounded-2xl
      backdrop-blur-2xl bg-white/[0.55]
      border border-white/70
      shadow-[0_6px_24px_rgba(139,111,71,0.08),0_2px_6px_rgba(139,111,71,0.04)]
      px-5 py-5 md:px-6 md:py-6
    ">
      {children}
    </div>
  );
}

function SkeletonTable() {
  return (
    <div className="space-y-4">
      <div className="flex gap-8 pb-3 border-b border-[#E5DDD0]/40">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="w-24 h-3 rounded bg-[#E5DDD0]/30 animate-pulse" />
        ))}
      </div>
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex gap-8 py-1">
          <div className="w-32 h-3 rounded bg-[#E5DDD0]/25 animate-pulse" />
          <div className="w-28 h-3 rounded bg-[#E5DDD0]/20 animate-pulse" />
          <div className="w-12 h-3 rounded bg-[#E5DDD0]/20 animate-pulse" />
          <div className="w-20 h-3 rounded bg-[#E5DDD0]/20 animate-pulse" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  icon,
  text,
  linkTo,
  linkLabel,
}: {
  icon: React.ReactNode;
  text: string;
  linkTo?: string;
  linkLabel?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-[#C9B89A]">
      <div className="opacity-25 mb-3">{icon}</div>
      <p className="text-[13px] text-[#A99B88]">{text}</p>
      {linkTo && linkLabel && (
        <Link
          to={linkTo}
          className="mt-2.5 text-[12px] tracking-wide text-[#B8985F] hover:text-[#8B6F47] transition-colors"
        >
          {linkLabel}
        </Link>
      )}
    </div>
  );
}
