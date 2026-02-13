import { Link } from "react-router";
import { Package, Users, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { getDashboardStats } from "../../src/lib/api/dashboard";

export function Dashboard() {
  const [stats, setStats] = useState({
    total_tours: 0,
    total_pilgrims: 0,
    sent_jobs: 0,
  });
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadStats = async () => {
      setIsLoadingStats(true);
      try {
        const data = await getDashboardStats();
        if (!cancelled) setStats(data);
      } catch (error) {
        console.error("Error loading dashboard stats:", error);
      } finally {
        if (!cancelled) setIsLoadingStats(false);
      }
    };

    loadStats();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="p-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl mb-2 text-[#2B2318]">Добро пожаловать</h1>
          <p className="text-[#6B5435]">
            Система управления тур кодами Hickmet Premium
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link
            to="/create"
            className="group relative overflow-hidden bg-white rounded-2xl p-8 shadow-md hover:shadow-xl transition-all duration-300 border border-[#E5DDD0]"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-[#B8985F]/10 to-transparent rounded-full -mr-16 -mt-16" />
            <div className="relative">
              <div className="w-14 h-14 bg-gradient-to-br from-[#B8985F] to-[#A88952] rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Plus className="w-7 h-7 text-white" />
              </div>
              <h3 className="mb-2 text-[#2B2318]">Создать тур код</h3>
              <p className="text-sm text-[#6B5435]">
                Создать новый тур код для паломников
              </p>
            </div>
          </Link>

          <Link
            to="/packages"
            className="group relative overflow-hidden bg-white rounded-2xl p-8 shadow-md hover:shadow-xl transition-all duration-300 border border-[#E5DDD0]"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-[#B8985F]/10 to-transparent rounded-full -mr-16 -mt-16" />
            <div className="relative">
              <div className="w-14 h-14 bg-gradient-to-br from-[#8B6F47] to-[#6B5435] rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Package className="w-7 h-7 text-white" />
              </div>
              <h3 className="mb-2 text-[#2B2318]">Пакеты с тур кодом</h3>
              <p className="text-sm text-[#6B5435]">
                Просмотр и управление пакетами
              </p>
            </div>
          </Link>

          <Link
            to="/pilgrims"
            className="group relative overflow-hidden bg-white rounded-2xl p-8 shadow-md hover:shadow-xl transition-all duration-300 border border-[#E5DDD0]"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-[#B8985F]/10 to-transparent rounded-full -mr-16 -mt-16" />
            <div className="relative">
              <div className="w-14 h-14 bg-gradient-to-br from-[#C9B89A] to-[#B8985F] rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Users className="w-7 h-7 text-white" />
              </div>
              <h3 className="mb-2 text-[#2B2318]">Паломники</h3>
              <p className="text-sm text-[#6B5435]">
                Управление списком паломников
              </p>
            </div>
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-[#B8985F] to-[#A88952] rounded-2xl p-6 text-white">
            <p className="text-sm opacity-90 mb-2">Всего туров</p>
            <p className="text-3xl">{isLoadingStats ? "..." : stats.total_tours}</p>
          </div>
          <div className="bg-gradient-to-br from-[#8B6F47] to-[#6B5435] rounded-2xl p-6 text-white">
            <p className="text-sm opacity-90 mb-2">Активных паломников</p>
            <p className="text-3xl">{isLoadingStats ? "..." : stats.total_pilgrims}</p>
          </div>
          <div className="bg-gradient-to-br from-[#C9B89A] to-[#B8985F] rounded-2xl p-6 text-white">
            <p className="text-sm opacity-90 mb-2">Успешных отправок</p>
            <p className="text-3xl">{isLoadingStats ? "..." : stats.sent_jobs}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
