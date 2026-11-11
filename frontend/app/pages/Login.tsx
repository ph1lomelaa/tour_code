import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { Loader2 } from "lucide-react";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { AuthShell, AUTH_BUTTON, AUTH_INPUT } from "../components/AuthShell";
import { useAuth } from "../context/AuthContext";
import { login } from "../../src/lib/api/auth";
import { errorDetail } from "../../src/lib/api/settings";

const safeNext = (next: string | null) => (next && next.startsWith("/") && !next.startsWith("//") ? next : "/");

export function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get("next"));

  if (user) return <Navigate to={next} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      signIn(await login(email.trim(), password));
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorDetail(err, "Не удалось войти"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Вход" subtitle="Войдите с почтой и паролем, которые вы задали по ссылке-приглашению.">
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email" className="text-sm text-brand-text">Почта</Label>
          <Input id="email" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} className={AUTH_INPUT} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password" className="text-sm text-brand-text">Пароль</Label>
          <Input id="password" type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} className={AUTH_INPUT} />
        </div>
        {error && <p className="rounded-lg bg-brand-alert-soft px-3 py-2 text-sm text-brand-alert">{error}</p>}
        <Button type="submit" disabled={busy} className={AUTH_BUTTON}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Войти
        </Button>
        <p className="text-center text-xs text-brand-muted">
          Нет доступа или забыли пароль? Попросите администратора прислать новую ссылку.
        </p>
      </form>
    </AuthShell>
  );
}
