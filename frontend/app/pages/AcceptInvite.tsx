import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Loader2 } from "lucide-react";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { AuthShell, AUTH_BUTTON, AUTH_INPUT } from "../components/AuthShell";
import { useAuth } from "../context/AuthContext";
import { acceptInvite, getInvite } from "../../src/lib/api/auth";
import { errorDetail } from "../../src/lib/api/settings";

const MIN_PASSWORD = 8;

export function AcceptInvite() {
  const { token = "" } = useParams();
  const { signIn, signOut } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState<string | null>(null);
  const [loadError, setLoadError] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getInvite(token)
      .then((info) => {
        setEmail(info.email);
        setFullName(info.full_name);
      })
      .catch((err) => setLoadError(errorDetail(err, "Ссылка недействительна")));
  }, [token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Пароль — минимум ${MIN_PASSWORD} символов`);
    if (password !== repeat) return setError("Пароли не совпадают");
    setBusy(true);
    setError("");
    try {
      signOut();
      signIn(await acceptInvite(token, fullName.trim(), password));
      navigate("/", { replace: true });
    } catch (err) {
      setError(errorDetail(err, "Не удалось сохранить пароль"));
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <AuthShell title="Ссылка не работает" subtitle={loadError}>
        <p className="mb-6 text-sm text-brand-text">
          Ссылка уже использована или заменена новой. Попросите администратора прислать новую ссылку.
        </p>
        <Link to="/login" className="text-sm text-brand-accent hover:underline">Перейти ко входу</Link>
      </AuthShell>
    );
  }

  if (email === null) {
    return (
      <AuthShell title="Приглашение">
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-brand-accent" />
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Добро пожаловать" subtitle="Задайте имя и пароль — дальше входите по почте и этому паролю.">
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label className="text-sm text-brand-text">Почта (логин)</Label>
          <Input value={email} disabled className={`${AUTH_INPUT} opacity-80`} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name" className="text-sm text-brand-text">Имя и фамилия</Label>
          <Input id="name" required autoComplete="name" value={fullName}
            onChange={(e) => setFullName(e.target.value)} className={AUTH_INPUT} />
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
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Сохранить и войти
        </Button>
      </form>
    </AuthShell>
  );
}
