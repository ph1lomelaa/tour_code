import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { Loader2 } from "lucide-react";
import { getMe, TOKEN_KEY, type AppUser, type AuthSession } from "../../src/lib/api/auth";

interface AuthState {
  user: AppUser | null;
  loading: boolean;
  canEdit: boolean;
  isAdmin: boolean;
  signIn: (session: AuthSession) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const readToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(() => Boolean(readToken()));

  useEffect(() => {
    if (!readToken()) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = () => {
      getMe()
        .then((me) => {
          if (cancelled) return;
          setUser(me);
          setLoading(false);
        })
        .catch((err) => {
          if (cancelled) return;
          // Выходим только если сервер сказал «не пускать» (401). При обрыве сети
          // или перезапуске сервера токен сохраняем и пробуем снова — вход не слетает.
          if (err?.response?.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            setUser(null);
            setLoading(false);
          } else {
            timer = setTimeout(check, 3000);
          }
        });
    };
    check();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const signIn = useCallback((session: AuthSession) => {
    localStorage.setItem(TOKEN_KEY, session.access_token);
    setUser(session.user);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      canEdit: user?.role === "admin" || user?.role === "editor",
      isAdmin: user?.role === "admin",
      signIn,
      signOut,
    }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

function FullScreenLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-brand-cream">
      <Loader2 className="h-6 w-6 animate-spin text-brand-accent" />
    </div>
  );
}

/** Пускает внутрь только вошедших. */
export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullScreenLoader />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <Outlet />;
}

/** Только для администратора. */
export function RequireAdmin() {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/" replace />;
  return <Outlet />;
}
