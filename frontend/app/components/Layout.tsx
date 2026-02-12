import { Outlet, Link, useLocation } from "react-router";
import { Package, Users, Plus, Menu, Home } from "lucide-react";
import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "./ui/sheet";
import { Button } from "./ui/button";

export function Layout() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const menuItems = [
    {
      path: "/create",
      label: "Создать тур код для паломников",
      icon: Plus,
    },
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
  ];

  const SidebarContent = () => (
    <>
      {/* Logo - now clickable to go home */}
      <Link
        to="/"
        className="p-8 border-b border-[#4A3E32] hover:bg-[#4A3E32]/30 transition-colors"
        onClick={() => setMobileMenuOpen(false)}
      >
        <h1 className="text-xl tracking-[0.2em] mb-1 text-[#D4C5B0]">HICKMET</h1>
        <p className="text-xs tracking-[0.3em] text-[#B8985F]">PREMIUM</p>
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
                    ? "bg-gradient-to-r from-[#B8985F] to-[#A88952] text-white shadow-lg"
                    : "hover:bg-[#4A3E32] text-[#D4C5B0]"
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
                        ? "bg-gradient-to-r from-[#B8985F] to-[#A88952] text-white shadow-lg"
                        : "hover:bg-[#4A3E32] text-[#D4C5B0]"
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

      {/* Footer */}
      <div className="p-6 border-t border-[#4A3E32]">
        <p className="text-xs text-[#8B6F47] text-center">
          © 2026 Hickmet Premium
        </p>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-[#F5F1EA]">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-80 bg-gradient-to-b from-[#2B2318] to-[#3D3127] text-[#F5F1EA] flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-gradient-to-r from-[#2B2318] to-[#3D3127] text-[#F5F1EA] px-4 py-4 shadow-lg">
        <div className="flex items-center justify-between">
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="text-[#D4C5B0] hover:bg-[#4A3E32]"
              >
                <Menu className="w-6 h-6" />
              </Button>
            </SheetTrigger>
            <SheetContent
              side="left"
              className="w-80 p-0 bg-gradient-to-b from-[#2B2318] to-[#3D3127] text-[#F5F1EA] border-[#4A3E32]"
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
            <h1 className="text-base tracking-[0.2em] text-[#D4C5B0]">HICKMET</h1>
            <p className="text-[10px] tracking-[0.3em] text-[#B8985F]">PREMIUM</p>
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