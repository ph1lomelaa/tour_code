import { useCallback, useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Copy, Loader2, Plus, Power, RefreshCw, Trash2, UserPlus } from "lucide-react";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS, type AppUser, type UserRole } from "../../src/lib/api/auth";
import {
  createUser, deleteUser, inviteLink, listUsers, regenerateInvite, updateUser,
} from "../../src/lib/api/users";
import { errorDetail } from "../../src/lib/api/settings";

const CARD = "bg-white rounded-2xl p-6 shadow-lg border border-brand-line";
const PRIMARY = "bg-brand-accent text-white hover:bg-brand-accent-hover";
const ROLES: UserRole[] = ["viewer", "editor", "admin"];

const ROLE_HINTS: Record<UserRole, string> = {
  viewer: "Видит всё, но ничего не меняет",
  editor: "Создаёт тур-коды и меняет данные",
  admin: "Всё + управление пользователями",
};

const STATUS: Record<AppUser["status"], { label: string; tone: string }> = {
  invited: { label: "Приглашён", tone: "bg-brand-accent-soft text-brand-accent border-brand-accent-200" },
  active: { label: "Активен", tone: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  disabled: { label: "Отключён", tone: "bg-brand-cream-2 text-brand-muted border-brand-line-strong" },
};

const formatDate = (value: string | null) =>
  value ? new Date(value + (value.endsWith("Z") ? "" : "Z")).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : "—";

/** Копирование, которое работает и на http (без https), где navigator.clipboard недоступен. */
function copyFallback(text: string): boolean {
  // Кладём текст в буфер прямо в событии copy — не зависит от выделения и фокуса.
  const onCopy = (e: ClipboardEvent) => {
    e.clipboardData?.setData("text/plain", text);
    e.preventDefault();
  };
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.top = "-1000px";
  document.body.appendChild(area);
  area.focus();
  area.select();
  document.addEventListener("copy", onCopy);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.removeEventListener("copy", onCopy);
  document.body.removeChild(area);
  return ok;
}

async function copy(text: string) {
  let ok = false;
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = false;
    }
  }
  if (!ok) ok = copyFallback(text);
  if (ok) toast.success("Ссылка скопирована");
  else toast.error("Не удалось скопировать — выделите ссылку вручную");
}

function LinkBox({ link }: { link: string }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input readOnly value={link} onFocus={(e) => e.target.select()} className="bg-brand-card text-xs" />
        <Button type="button" className={PRIMARY} onClick={() => copy(link)}>
          <Copy className="h-4 w-4" /> Копировать
        </Button>
      </div>
      <p className="text-xs text-brand-muted">
        Отправьте ссылку человеку. По ней он задаст имя и пароль. Ссылка работает, пока человек не зарегистрируется.
      </p>
    </div>
  );
}

export function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AppUser[] | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<{ email: string; url: string } | null>(null);
  const [toDelete, setToDelete] = useState<AppUser | null>(null);
  const [toRegenerate, setToRegenerate] = useState<AppUser | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await listUsers());
    } catch (e) {
      toast.error(errorDetail(e, "Не удалось загрузить пользователей"));
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const replace = (u: AppUser) => setUsers((list) => list?.map((x) => (x.id === u.id ? u : x)) ?? null);

  const submitCreate = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await createUser(email.trim(), role);
      setUsers((list) => [...(list ?? []), res.user]);
      setCreateOpen(false);
      setLink({ email: res.user.email, url: inviteLink(res.invite_token) });
      setEmail("");
      setRole("viewer");
    } catch (err) {
      toast.error(errorDetail(err, "Не удалось добавить"));
    } finally {
      setBusy(false);
    }
  };

  const changeRole = async (u: AppUser, next: UserRole) => {
    try {
      replace(await updateUser(u.id, { role: next }));
      toast.success(`${u.email}: ${ROLE_LABELS[next]}`);
    } catch (err) {
      toast.error(errorDetail(err));
    }
  };

  const toggleActive = async (u: AppUser) => {
    try {
      replace(await updateUser(u.id, { is_active: u.status === "disabled" }));
    } catch (err) {
      toast.error(errorDetail(err));
    }
  };

  const newLink = async (u: AppUser) => {
    setToRegenerate(null);
    try {
      const res = await regenerateInvite(u.id);
      replace(res.user);
      setLink({ email: u.email, url: inviteLink(res.invite_token) });
    } catch (err) {
      toast.error(errorDetail(err));
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      const res = await deleteUser(toDelete.id);
      toast.success(res.disabled ? "У пользователя есть туры — он отключён, а не удалён" : "Удалено");
      await load();
    } catch (err) {
      toast.error(errorDetail(err));
    } finally {
      setToDelete(null);
    }
  };

  return (
    <div className="p-4 md:p-12">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl mb-2 text-brand-ink">Пользователи</h1>
            <p className="text-brand-text">Кто имеет доступ к системе. Новых сотрудников добавляйте по почте и отправляйте им ссылку.</p>
          </div>
          <Button className={PRIMARY} onClick={() => setCreateOpen(true)}>
            <UserPlus className="h-4 w-4" /> Добавить пользователя
          </Button>
        </div>

        <div className={CARD}>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Почта</TableHead>
                  <TableHead>Имя</TableHead>
                  <TableHead>Доступ</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Последний вход</TableHead>
                  <TableHead className="text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users === null && (
                  <TableRow><TableCell colSpan={6} className="text-center"><Loader2 className="inline h-4 w-4 animate-spin" /></TableCell></TableRow>
                )}
                {users?.map((u) => {
                  const isMe = u.id === me?.id;
                  const status = STATUS[u.status];
                  return (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium text-brand-ink">
                        {u.email}
                        {isMe && <span className="ml-2 text-xs text-brand-muted">(вы)</span>}
                      </TableCell>
                      <TableCell className="text-brand-text">{u.full_name || "—"}</TableCell>
                      <TableCell>
                        <Select value={u.role} disabled={isMe} onValueChange={(v) => changeRole(u, v as UserRole)}>
                          <SelectTrigger className="h-9 w-36 bg-brand-card"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {ROLES.map((r) => <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs ${status.tone}`}>{status.label}</span>
                      </TableCell>
                      <TableCell className="text-xs text-brand-muted">{formatDate(u.last_login_at)}</TableCell>
                      <TableCell>
                        {!isMe && (
                          <div className="flex justify-end gap-1">
                            {u.invite_token && (
                              <Button variant="ghost" size="sm" title="Скопировать ссылку" onClick={() => copy(inviteLink(u.invite_token!))}>
                                <Copy className="h-4 w-4" /> <span className="hidden xl:inline">Ссылка</span>
                              </Button>
                            )}
                            <Button variant="ghost" size="sm" title="Новая ссылка (если старая потерялась или нужно сбросить пароль)" onClick={() => setToRegenerate(u)}>
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" title={u.status === "disabled" ? "Включить" : "Отключить"} onClick={() => toggleActive(u)}>
                              <Power className={`h-4 w-4 ${u.status === "disabled" ? "text-emerald-600" : ""}`} />
                            </Button>
                            <Button variant="ghost" size="sm" title="Удалить" onClick={() => setToDelete(u)}>
                              <Trash2 className="h-4 w-4 text-brand-alert" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r} className="rounded-xl border border-brand-line bg-brand-card p-4">
              <p className="font-serif text-brand-ink">{ROLE_LABELS[r]}</p>
              <p className="text-sm text-brand-text">{ROLE_HINTS[r]}</p>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form onSubmit={submitCreate}>
            <DialogHeader>
              <DialogTitle>Новый пользователь</DialogTitle>
              <DialogDescription>После добавления появится ссылка — отправьте её человеку.</DialogDescription>
            </DialogHeader>
            <div className="my-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new-email">Почта</Label>
                <Input id="new-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Доступ</Label>
                <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => (
                      <SelectItem key={r} value={r}>{ROLE_LABELS[r]} — {ROLE_HINTS[r].toLowerCase()}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={busy} className={PRIMARY}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Создать ссылку
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={link !== null} onOpenChange={(open) => !open && setLink(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ссылка для {link?.email}</DialogTitle>
            <DialogDescription>Ссылку можно скопировать ещё раз в любой момент — кнопкой «Ссылка» в списке.</DialogDescription>
          </DialogHeader>
          {link && <LinkBox link={link.url} />}
        </DialogContent>
      </Dialog>

      <AlertDialog open={toRegenerate !== null} onOpenChange={(open) => !open && setToRegenerate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Новая ссылка для {toRegenerate?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              Старая ссылка перестанет работать. Нужно, если ссылка потерялась или человек забыл пароль.
              Чтобы просто отправить ту же ссылку ещё раз, нажмите «Ссылка».
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <Button className={PRIMARY} onClick={() => toRegenerate && newLink(toRegenerate)}>Создать новую</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={toDelete !== null} onOpenChange={(open) => !open && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить {toDelete?.email}?</AlertDialogTitle>
            <AlertDialogDescription>Пользователь сразу потеряет доступ.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <Button className="bg-brand-alert text-white hover:bg-brand-alert" onClick={confirmDelete}>Удалить</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
