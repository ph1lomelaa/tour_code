import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router";
import { Loader2 } from "lucide-react";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { AuthShell, AUTH_BUTTON, AUTH_INPUT } from "../components/AuthShell";
import { useAuth } from "../context/AuthContext";
import { requestAccess } from "../../src/lib/api/auth";
import { errorDetail } from "../../src/lib/api/settings";

const MIN_PASSWORD = 8;

export function RequestAccess() {
  const { user } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Пароль — минимум ${MIN_PASSWORD} символов`);
    if (password !== repeat) return setError("Пароли не совпадают");
    setBusy(true);
    setError("");
    try {
      await requestAccess(fullName.trim(), email.trim(), password);
      setSent(true);
    } catch (err) {
      setError(errorDetail(err, "Не удалось отправить заявку"));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <AuthShell title="Заявка отправлена" subtitle="Администратор рассмотрит её и откроет доступ.">
        <p className="mb-6 text-sm text-brand-text">
          После одобрения входите по почте <span className="font-medium">{email.trim().toLowerCase()}</span> и
          паролю, который вы указали.
        </p>
        <Link to="/login" className="text-sm text-brand-accent hover:underline">Перейти ко входу</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Запросить доступ" subtitle="Заполните данные — администратор получит заявку.">
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name" className="text-sm text-brand-text">Имя и фамилия</Label>
          <Input id="name" required autoComplete="name" value={fullName}
            onChange={(e) => setFullName(e.target.value)} className={AUTH_INPUT} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email" className="text-sm text-brand-text">Почта</Label>
          <Input id="email" type="email" required autoComplete="email" value={email}
            onChange={(e) => setEmail(e.target.value)} className={AUTH_INPUT} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password" className="text-sm text-brand-text">Пароль</Label>
          <Input id="password" type="password" autoComplete="new-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} className={AUTH_INPUT} />
          <p className="text-xs text-brand-muted">Не короче {MIN_PASSWORD} символов</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="repeat" className="text-sm text-brand-text">Повторите пароль</Label>
          <Input id="repeat" type="password" autoComplete="new-password" required value={repeat}
            onChange={(e) => setRepeat(e.target.value)} className={AUTH_INPUT} />
        </div>
        {error && <p className="rounded-lg bg-brand-alert-soft px-3 py-2 text-sm text-brand-alert">{error}</p>}
        <Button type="submit" disabled={busy} className={AUTH_BUTTON}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Отправить заявку
        </Button>
        <p className="text-center text-sm text-brand-muted">
          Уже есть доступ? <Link to="/login" className="text-brand-accent hover:underline">Войти</Link>
        </p>
      </form>
    </AuthShell>
  );
}
