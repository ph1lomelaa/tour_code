import { Outlet, Link, useLocation, useNavigate } from "react-router";
import { Package, Users, Plus, Menu, Home, Settings, ShieldCheck, LogOut } from "lucide-react";
import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "./ui/sheet";
import { Button } from "./ui/button";
import { useAuth } from "../context/AuthContext";
import { StarPattern } from "./Ornament";
import { ROLE_LABELS } from "../../src/lib/api/auth";

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAdmin, canEdit, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    signOut();
    navigate("/login", { replace: true });
  };

  const menuItems = [
    ...(canEdit
      ? [
          {
            path: "/create",
            label: "Создать тур код для паломников",
            icon: Plus,
          },
        ]
      : []),
    {
      path: "/packages",
      label: "Пакеты с тур кодом",
      icon: Package,
    },
    {
      path: "/pilgrims",
      label: "Паломники",
      icon: Users,
    },
    {
      path: "/settings",
      label: "Настройки",
      icon: Settings,
    },
    ...(isAdmin
      ? [
          {
            path: "/users",
            label: "Пользователи",
            icon: ShieldCheck,
          },
        ]
      : []),
  ];

  const SidebarContent = () => (
    <>
      {/* Logo - now clickable to go home */}
      <Link
        to="/"
        className="p-8 border-b border-white/15 hover:bg-white/10 transition-colors"
        onClick={() => setMobileMenuOpen(false)}
      >
        <h1 className="text-xl tracking-[0.2em] mb-1 text-white">HICKMET</h1>
        <p className="text-xs tracking-[0.3em] text-[#f3dfa8]">PREMIUM</p>
      </Link>

      {/* Menu */}
      <nav className="flex-1 px-4 py-8">
        <ul className="space-y-2">
          {/* Home button */}
          <li>
            <Link
              to="/"
              onClick={() => setMobileMenuOpen(false)}
              className={`
                flex items-center gap-4 px-6 py-4 rounded-lg transition-all duration-200
                ${
                  location.pathname === "/"
                    ? "bg-brand-cream text-brand-ink shadow-lg"
                    : "hover:bg-white/10 text-white"
                }
              `}
            >
              <Home className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">Главная</span>
            </Link>
          </li>

          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`
                    flex items-center gap-4 px-6 py-4 rounded-lg transition-all duration-200
                    ${
                      isActive
                        ? "bg-brand-cream text-brand-ink shadow-lg"
                        : "hover:bg-white/10 text-white"
                    }
                  `}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer: текущий пользователь */}
      <div className="p-6 border-t border-white/15">
        {user && (
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm text-white">{user.full_name || user.email}</p>
              <p className="text-xs text-[#f3dfa8]">{ROLE_LABELS[user.role]}</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Выйти"
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-white hover:bg-white/10 transition-colors"
            >
              <LogOut className="w-4 h-4" /> Выйти
            </button>
          </div>
        )}
        <p className="text-xs text-white/60 text-center">
          © 2026 Hickmet Premium
        </p>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-brand-cream">
      {/* Desktop Sidebar */}
      <aside className="relative hidden md:flex w-80 overflow-hidden bg-gradient-to-b from-brand-mocha to-brand-mocha-2 text-brand-cream">
        <StarPattern color="#f6ebdd" className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.12]" />
        <div className="relative flex w-full flex-col">
          <SidebarContent />
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-gradient-to-r from-brand-mocha to-brand-mocha-2 text-brand-cream px-4 py-4 shadow-lg">
        <div className="flex items-center justify-between">
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="text-white hover:bg-white/10"
              >
                <Menu className="w-6 h-6" />
              </Button>
            </SheetTrigger>
            <SheetContent
              side="left"
              className="w-80 p-0 bg-gradient-to-b from-brand-mocha to-brand-mocha-2 text-brand-cream border-white/15"
            >
              <SheetTitle className="sr-only">Меню навигации</SheetTitle>
              <SheetDescription className="sr-only">
                Выберите раздел для навигации
              </SheetDescription>
              <div className="flex flex-col h-full">
                <SidebarContent />
              </div>
            </SheetContent>
          </Sheet>

          <Link to="/" className="flex flex-col items-center">
            <h1 className="text-base tracking-[0.2em] text-white">HICKMET</h1>
            <p className="text-[10px] tracking-[0.3em] text-[#f3dfa8]">PREMIUM</p>
          </Link>

          <div className="w-10" /> {/* Spacer for centering */}
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto pt-0 md:pt-0">
        <div className="md:hidden h-16" /> {/* Spacer for mobile header */}
        <Outlet />
      </main>
    </div>
  );
}