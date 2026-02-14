import { Link } from "react-router";
import {
  Package,
  Users,
  Plus,
  Plane,
  CheckCircle2,
  ArrowRight,
  Send,
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

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
  } catch {
    return "";
  }
}

export function Dashboard() {
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
          <header className="mb-12">
            <p className="text-[10px] font-semibold tracking-[0.4em] uppercase text-[#C4A265] mb-4">
              Hickmet Premium
            </p>
            <h1 className="text-3xl md:text-[40px] leading-tight font-light text-[#3D2E1C] mb-3" style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}>
              Ассаляму алейкум
            </h1>
            <p className="text-[15px] text-[#8B7A63] max-w-md tracking-wide">
              Управление тур кодами для паломников
            </p>
          </header>

          {/* ── Quick actions ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5 mb-10">
            <ActionCard
              to="/create"
              icon={<Plus className="w-5 h-5" />}
              title="Создать тур код"
              subtitle="Создать новый тур код для паломников"
            />
            <ActionCard
              to="/packages"
              icon={<Package className="w-5 h-5" />}
              title="Пакеты с тур кодом"
              subtitle="Просмотр и управление пакетами"
            />
            <ActionCard
              to="/pilgrims"
              icon={<Users className="w-5 h-5" />}
              title="Паломники"
              subtitle="Управление списком паломников"
            />
          </div>

          {/* ── Stats ── */}
          <div className="grid grid-cols-3 gap-3 md:gap-5 mb-12">
            <GlassStat
              value={stats.total_tours}
              label="Всего туров"
              icon={<Package className="w-4 h-4" />}
              isLoading={isLoading}
            />
            <GlassStat
              value={stats.total_pilgrims}
              label="Активных паломников"
              icon={<Users className="w-4 h-4" />}
              isLoading={isLoading}
            />
            <GlassStat
              value={stats.sent_jobs}
              label="Успешных отправок"
              icon={<Send className="w-4 h-4" />}
              isLoading={isLoading}
            />
          </div>

          {/* ── Activity ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Recent Tours */}
            <GlassPanel>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-[13px] tracking-[0.15em] uppercase text-[#8B6F47]">
                  Последние туры
                </h3>
                <Link
                  to="/packages"
                  className="text-[12px] text-[#B8985F] hover:text-[#8B6F47] flex items-center gap-1 transition-colors"
                >
                  Все туры <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {isLoading ? (
                <SkeletonList />
              ) : recentTours.length === 0 ? (
                <EmptyState
                  icon={<Plane className="w-8 h-8" />}
                  text="Туров пока нет"
                  linkTo="/create"
                  linkLabel="Создать первый"
                />
              ) : (
                <ul className="space-y-1">
                  {recentTours.map((tour) => (
                    <li key={tour.id}>
                      <Link
                        to={`/create?tourId=${tour.id}`}
                        className="group flex items-center gap-3.5 px-3.5 py-3 -mx-1 rounded-xl hover:bg-white/50 transition-all duration-200"
                      >
                        <div className="w-9 h-9 rounded-[10px] bg-gradient-to-br from-[#C4A265]/20 to-[#B8985F]/5 flex items-center justify-center flex-shrink-0">
                          <Plane className="w-4 h-4 text-[#B8985F]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] text-[#2B2318] truncate leading-tight">
                            {tour.sheet_name || tour.route || "Тур"}
                          </p>
                          <p className="text-[11px] text-[#A99B88] mt-0.5">
                            {tour.date_start} — {tour.date_end}
                            <span className="mx-1.5 opacity-40">|</span>
                            {tour.pilgrims_count} чел.
                          </p>
                        </div>
                        <StatusDot status={tour.dispatch_status} />
                        <ArrowRight className="w-3.5 h-3.5 text-[#D4C5B0] opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </GlassPanel>

            {/* Recent Jobs */}
            <GlassPanel>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-[13px] tracking-[0.15em] uppercase text-[#8B6F47]">
                  Отправки
                </h3>
              </div>

              {isLoading ? (
                <SkeletonList />
              ) : recentJobs.length === 0 ? (
                <EmptyState
                  icon={<CheckCircle2 className="w-8 h-8" />}
                  text="Отправок пока нет"
                />
              ) : (
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
                          {formatDate(job.created_at)}
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
              )}
            </GlassPanel>
          </div>
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
  icon,
  isLoading,
}: {
  value: number;
  label: string;
  icon: React.ReactNode;
  isLoading: boolean;
}) {
  return (
    <div className="
      relative overflow-hidden rounded-xl
      backdrop-blur-2xl bg-white/[0.55]
      border border-white/70
      shadow-[0_4px_20px_rgba(139,111,71,0.08),0_1px_3px_rgba(139,111,71,0.04)]
      px-4 py-4 md:px-5 md:py-4
      transition-all duration-300 hover:bg-white/70 hover:shadow-[0_6px_24px_rgba(139,111,71,0.12)]
    ">
      <div className="relative flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#C4A265]/20 to-[#B8985F]/10 flex items-center justify-center text-[#B8985F]">
          {icon}
        </div>
        <div>
          <p className="text-[22px] md:text-[26px] leading-none text-[#2B2318] tracking-tight font-medium">
            {isLoading ? (
              <span className="inline-block w-8 h-6 rounded-md bg-[#E5DDD0]/40 animate-pulse" />
            ) : (
              value
            )}
          </p>
          <p className="text-[10px] tracking-[0.08em] uppercase text-[#9C8B75] mt-1">{label}</p>
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
        px-6 py-6 md:px-7 md:py-7
        transition-all duration-300
        hover:bg-white/70 hover:shadow-[0_10px_36px_rgba(139,111,71,0.14)] hover:-translate-y-px
      "
    >
      {/* Hover copper glow */}
      <div className="absolute -bottom-10 -right-10 w-32 h-32 rounded-full bg-gradient-to-br from-[#C4A265] to-[#B8985F] opacity-0 group-hover:opacity-[0.08] blur-2xl transition-opacity duration-500" />

      <div className="relative flex items-center gap-5">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#C4A265] to-[#A88952] text-white flex items-center justify-center flex-shrink-0 shadow-[0_4px_16px_rgba(139,111,71,0.25)] group-hover:shadow-[0_6px_24px_rgba(139,111,71,0.35)] group-hover:scale-[1.03] transition-all duration-300">
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-[15px] font-medium text-[#2B2318] leading-tight mb-1 group-hover:text-[#8B6F47] transition-colors">
            {title}
          </h3>
          <p className="text-[13px] text-[#9C8B75] leading-snug">{subtitle}</p>
        </div>
        <ArrowRight className="w-4.5 h-4.5 text-[#C4A265]/50 group-hover:text-[#B8985F] group-hover:translate-x-0.5 transition-all flex-shrink-0" />
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

function SkeletonList() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-3.5 px-3.5 py-3">
          <div className="w-9 h-9 rounded-[10px] bg-[#E5DDD0]/30 animate-pulse" />
          <div className="flex-1 space-y-1.5">
            <div className="w-2/3 h-3 rounded bg-[#E5DDD0]/30 animate-pulse" />
            <div className="w-1/3 h-2.5 rounded bg-[#E5DDD0]/20 animate-pulse" />
          </div>
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
