import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2, CircleHelp, KeyRound, Loader2, Pencil, Plus, RotateCcw, Star, Trash2, XCircle,
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { Switch } from "../components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "../components/ui/alert-dialog";
import {
  AuditItem, FailedDispatchJob, KamkorAccount, ReferenceEntity, ReferenceItem, Verification,
  checkKamkorAccounts, createEntity, deleteEntity, errorDetail, getAuditLog, getFailedDispatchJobs,
  listEntity, restoreEntity, updateEntity, verifyEntity,
} from "../../src/lib/api/settings";
import { retryDispatchJob } from "../../src/lib/api/dispatch";
import { invalidateReferenceData } from "../hooks/useReferenceData";

type FieldKey = "code" | "name" | "name_ru" | "name_en" | "city" | "departure_city" | "bin";

interface EntityConfig {
  tab: string;
  singular: string; // «Удалить авиалинию …»
  fields: { key: FieldKey; label: string; placeholder?: string; required?: boolean }[];
  title: (item: Partial<ReferenceItem>) => string;
  // Поле, в которое подставляется подсказка Камкора.
  suggestTo: FieldKey;
}

const ENTITIES: Record<ReferenceEntity, EntityConfig> = {
  airlines: {
    tab: "Авиалинии",
    singular: "авиалинию",
    fields: [
      { key: "code", label: "Код (как на Камкоре)", placeholder: "KC", required: true },
      { key: "name", label: "Название", placeholder: "Air Astana" },
    ],
    title: (i) => (i.name ? `${i.code} — ${i.name}` : i.code || ""),
    suggestTo: "code",
  },
  countries: {
    tab: "Страны",
    singular: "страну",
    fields: [
      { key: "name_ru", label: "Название (как на Камкоре)", placeholder: "Саудовская Аравия", required: true },
      { key: "name_en", label: "Название на английском", placeholder: "Saudi Arabia" },
    ],
    title: (i) => i.name_ru || "",
    suggestTo: "name_ru",
  },
  hotels: {
    tab: "Отели",
    singular: "отель",
    fields: [
      { key: "name", label: "Название", placeholder: "Swissotel Makkah", required: true },
      { key: "city", label: "Город", placeholder: "Makkah" },
    ],
    title: (i) => i.name || "",
    suggestTo: "name",
  },
  routes: {
    tab: "Маршруты",
    singular: "маршрут",
    fields: [
      { key: "code", label: "Маршрут", placeholder: "ALA-JED или ALA-DOH-JED", required: true },
      { key: "departure_city", label: "Город вылета", placeholder: "Almaty" },
    ],
    title: (i) => i.code || "",
    suggestTo: "code",
  },
  touragents: {
    tab: "Турагенты",
    singular: "турагента",
    fields: [
      { key: "bin", label: "БИН", placeholder: "12 цифр", required: true },
      { key: "name", label: "Название", placeholder: "подставится из реестра Камкора" },
    ],
    title: (i) => i.name || i.bin || "",
    suggestTo: "name",
  },
};

const ENTITY_ORDER: ReferenceEntity[] = ["airlines", "countries", "hotels", "routes", "touragents"];

const ACTION_LABELS: Record<AuditItem["action"], string> = {
  create: "Добавлено",
  update: "Изменено",
  delete: "Удалено",
  restore: "Восстановлено",
};

const formatDate = (value?: string | null) =>
  value ? new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`).toLocaleString("ru-RU") : "—";

const CARD = "bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]";
const PRIMARY = "bg-[#B8985F] text-white hover:bg-[#a0834f]";

// ── Результат проверки Камкора ──────────────────────────

function VerificationView({ result, onSuggestion }: { result: Verification; onSuggestion: (value: string) => void }) {
  const meta = {
    found: { icon: CheckCircle2, tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
    not_found: { icon: XCircle, tone: "text-red-700 bg-red-50 border-red-200" },
    invalid: { icon: XCircle, tone: "text-red-700 bg-red-50 border-red-200" },
    unchecked: { icon: CircleHelp, tone: "text-stone-700 bg-stone-50 border-stone-200" },
  }[result.status];
  const Icon = meta.icon;

  return (
    <div className={`rounded-lg border p-3 text-sm ${meta.tone}`}>
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>{result.message}</span>
      </div>
      {result.suggestions.length > 0 && (
        <div className="mt-3">
          <p className="mb-2 text-xs">Возможно, вы имели в виду:</p>
          <div className="flex flex-wrap gap-2">
            {result.suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSuggestion(s.split(" — ")[0])}
                className="rounded-full border border-current/30 bg-white px-3 py-1 text-xs hover:bg-[#F5F1EA]"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Вкладка справочника ─────────────────────────────────

type EditorState = { mode: "create" | "edit"; id?: string; values: Partial<Record<FieldKey, string>> };
type ConfirmState = { verification: Verification; sure: boolean };
type PendingAction =
  | { kind: "delete"; item: ReferenceItem; typed: string }
  | { kind: "default"; item: ReferenceItem };

function EntityTab({ entity }: { entity: ReferenceEntity }) {
  const config = ENTITIES[entity];
  const [items, setItems] = useState<ReferenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDeleted, setShowDeleted] = useState(false);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busy, setBusy] = useState(false);

  const handleError = useCallback((e: unknown, fallback: string) => {
    toast.error(errorDetail(e, fallback));
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listEntity(entity));
    } catch (e) {
      handleError(e, "Не удалось загрузить справочник");
    } finally {
      setLoading(false);
    }
  }, [entity, handleError]);

  useEffect(() => {
    reload();
  }, [reload]);

  const changed = async () => {
    invalidateReferenceData();
    await reload();
  };

  const missingRequired = editor
    ? config.fields.some((f) => f.required && !(editor.values[f.key] || "").trim())
    : true;

  // Шаг 1: проверка на Камкоре, затем окно подтверждения.
  const startConfirm = async () => {
    if (!editor || missingRequired) return;
    setBusy(true);
    try {
      const verification = await verifyEntity(entity, editor.values);
      // Пустые поля заполняем тем, что нашлось на Камкоре (название, name_en).
      const filled = { ...editor.values };
      for (const [key, value] of Object.entries(verification.extra || {})) {
        const field = config.fields.find((f) => f.key === key);
        if (field && !(filled[field.key] || "").trim() && value) filled[field.key] = value;
      }
      setEditor({ ...editor, values: filled });
      setConfirm({ verification, sure: false });
    } catch (e) {
      handleError(e, "Не удалось проверить на Камкоре");
    } finally {
      setBusy(false);
    }
  };

  // Шаг 2: сохранение после подтверждения.
  const save = async () => {
    if (!editor || !confirm) return;
    const force = confirm.verification.status === "not_found";
    setBusy(true);
    try {
      if (editor.mode === "create") await createEntity(entity, editor.values, force);
      else if (editor.id) await updateEntity(entity, editor.id, editor.values, force);
      toast.success(editor.mode === "create" ? "Добавлено" : "Сохранено");
      setConfirm(null);
      setEditor(null);
      await changed();
    } catch (e) {
      handleError(e, "Не удалось сохранить");
    } finally {
      setBusy(false);
    }
  };

  const runPending = async () => {
    if (!pending) return;
    const { item } = pending;
    setBusy(true);
    try {
      if (pending.kind === "delete") {
        await deleteEntity(entity, item.id);
        toast(`Удалено: ${config.title(item)}`, {
          action: {
            label: "Отменить",
            onClick: async () => {
              try {
                await restoreEntity(entity, item.id);
                await changed();
              } catch (e) {
                handleError(e, "Не удалось восстановить");
              }
            },
          },
        });
      } else {
        await updateEntity(entity, item.id, { is_default: true });
        toast.success(`По умолчанию: ${config.title(item)}`);
      }
      setPending(null);
      await changed();
    } catch (e) {
      handleError(e, "Не удалось выполнить действие");
    } finally {
      setBusy(false);
    }
  };

  const restore = async (item: ReferenceItem) => {
    try {
      await restoreEntity(entity, item.id);
      toast.success(`Восстановлено: ${config.title(item)}`);
      await changed();
    } catch (e) {
      handleError(e, "Не удалось восстановить");
    }
  };

  const visible = showDeleted ? items : items.filter((i) => i.is_active);
  const verification = confirm?.verification;
  const canSave = verification
    && verification.status !== "invalid"
    && (verification.status !== "not_found" || confirm.sure);
  const deleteNeedsTyping = entity === "touragents";

  return (
    <div className={CARD}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-[#6B5435]">
          <Switch checked={showDeleted} onCheckedChange={setShowDeleted} />
          Показать удалённые
        </label>
        <Button className={PRIMARY} onClick={() => setEditor({ mode: "create", values: {} })}>
          <Plus className="w-4 h-4" /> Добавить
        </Button>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {config.fields.map((f) => <TableHead key={f.key}>{f.label}</TableHead>)}
              <TableHead>Камкор</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={config.fields.length + 2} className="text-center text-[#6B5435]">
                <Loader2 className="inline w-4 h-4 animate-spin" />
              </TableCell></TableRow>
            )}
            {!loading && visible.length === 0 && (
              <TableRow><TableCell colSpan={config.fields.length + 2} className="text-center text-[#6B5435]">
                Пусто
              </TableCell></TableRow>
            )}
            {!loading && visible.map((item) => (
              <TableRow key={item.id} className={item.is_active ? "" : "opacity-50"}>
                {config.fields.map((f, idx) => (
                  <TableCell key={f.key} className="text-[#2B2318]">
                    {item[f.key] || "—"}
                    {idx === 0 && item.is_default && (
                      <span className="ml-2 rounded-full bg-[#F5F1EA] px-2 py-0.5 text-xs text-[#8B6F47]">по умолчанию</span>
                    )}
                    {idx === 0 && !item.is_active && (
                      <span className="ml-2 text-xs text-red-700">удалено</span>
                    )}
                  </TableCell>
                ))}
                <TableCell className="text-xs text-[#6B5435]">
                  {item.kamkor_verified_at ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700">
                      <CheckCircle2 className="w-3.5 h-3.5" /> проверено
                    </span>
                  ) : "—"}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {item.is_active ? (
                    <>
                      {entity === "touragents" && !item.is_default && (
                        <Button variant="ghost" size="icon" title="Сделать по умолчанию"
                          onClick={() => setPending({ kind: "default", item })}>
                          <Star className="w-4 h-4" />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" title="Изменить"
                        onClick={() => setEditor({
                          mode: "edit",
                          id: item.id,
                          values: Object.fromEntries(config.fields.map((f) => [f.key, item[f.key] || ""])),
                        })}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Удалить" className="text-red-700"
                        onClick={() => setPending({ kind: "delete", item, typed: "" })}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => restore(item)}>
                      <RotateCcw className="w-4 h-4" /> Восстановить
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Форма добавления / изменения */}
      <Dialog open={Boolean(editor) && !confirm} onOpenChange={(open) => !open && setEditor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editor?.mode === "create" ? `Добавить ${config.singular}` : `Изменить ${config.singular}`}</DialogTitle>
            <DialogDescription>Перед сохранением значение будет проверено на Камкоре.</DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              startConfirm();
            }}
          >
            {config.fields.map((f, idx) => (
              <div key={f.key}>
                <label className="mb-1 block text-sm text-[#2B2318]">
                  {f.label}{f.required && <span className="text-red-700"> *</span>}
                </label>
                <Input
                  autoFocus={idx === 0}
                  value={editor?.values[f.key] || ""}
                  placeholder={f.placeholder}
                  onChange={(e) => setEditor((prev) => prev && { ...prev, values: { ...prev.values, [f.key]: e.target.value } })}
                  className="bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
            ))}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditor(null)}>Отмена</Button>
              <Button type="submit" disabled={busy || missingRequired} className={PRIMARY}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Проверить на Камкоре"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Подтверждение добавления / изменения */}
      <AlertDialog open={Boolean(confirm)} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {editor?.mode === "create" ? "Добавить" : "Сохранить"} {config.singular} «{editor ? config.title(editor.values) : ""}»?
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm text-[#2B2318]">
                  {config.fields.map((f) => (
                    <div key={f.key} className="contents">
                      <dt className="text-[#6B5435]">{f.label}</dt>
                      <dd>{editor?.values[f.key] || "—"}</dd>
                    </div>
                  ))}
                </dl>
                {verification && (
                  <VerificationView
                    result={verification}
                    onSuggestion={(value) => {
                      setEditor((prev) => prev && { ...prev, values: { ...prev.values, [config.suggestTo]: value } });
                      setConfirm(null);
                    }}
                  />
                )}
                {verification?.status === "not_found" && (
                  <label className="flex items-center gap-2 text-sm text-[#2B2318]">
                    <Checkbox
                      checked={confirm?.sure}
                      onCheckedChange={(checked) => setConfirm((prev) => prev && { ...prev, sure: checked === true })}
                    />
                    Я уверен(а), всё равно сохранить
                  </label>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setConfirm(null)}>Назад</AlertDialogCancel>
            <Button disabled={!canSave || busy} className={PRIMARY} onClick={save}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : editor?.mode === "create" ? "Добавить" : "Сохранить"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Подтверждение удаления / смены «по умолчанию» */}
      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pending?.kind === "delete"
                ? `Удалить ${config.singular} «${config.title(pending.item)}»?`
                : `Сделать «${pending ? config.title(pending.item) : ""}» турагентом по умолчанию?`}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm">
                {pending?.kind === "delete" ? (
                  <p>
                    Значение исчезнет из выпадающих списков. Уже созданные туры не изменятся,
                    запись можно будет восстановить.
                  </p>
                ) : (
                  <p>Он будет подставляться при создании нового тур-кода.</p>
                )}
                {pending?.kind === "delete" && deleteNeedsTyping && (
                  <div>
                    <p className="mb-1">Для подтверждения введите название: <b>{pending.item.name}</b></p>
                    <Input
                      value={pending.typed}
                      onChange={(e) => setPending((prev) => prev && prev.kind === "delete" ? { ...prev, typed: e.target.value } : prev)}
                      className="bg-[#F5F1EA] border-[#E5DDD0]"
                    />
                  </div>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <Button
              disabled={busy || (pending?.kind === "delete" && deleteNeedsTyping && pending.typed.trim() !== pending.item.name)}
              className={pending?.kind === "delete" ? "bg-red-700 text-white hover:bg-red-800" : PRIMARY}
              onClick={runPending}
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : pending?.kind === "delete" ? "Удалить" : "Подтвердить"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ── Камкор: аккаунты входа и форма ──────────────────────

function KamkorTab() {
  const [accounts, setAccounts] = useState<KamkorAccount[] | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      setAccounts(await checkKamkorAccounts());
    } catch (e) {
      toast.error(errorDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className={CARD}>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-[#2B2318]">Аккаунты входа</h3>
            <p className="text-sm text-[#6B5435]">Логины и пароли хранятся в .env на сервере. Здесь можно проверить, что вход работает.</p>
          </div>
          <Button className={PRIMARY} disabled={busy} onClick={run}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
            Проверить вход
          </Button>
        </div>
        {accounts && (
          <ul className="space-y-2">
            {accounts.map((a) => (
              <li key={a.key} className="flex items-start gap-2 text-sm">
                {a.ok
                  ? <CheckCircle2 className="w-4 h-4 mt-0.5 text-emerald-700" />
                  : <XCircle className="w-4 h-4 mt-0.5 text-red-700" />}
                <span>
                  <b>{a.label}</b> ({a.login || "логин не задан"}) — {a.ok ? "вход работает" : a.error}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

    </div>
  );
}

// ── Упавшие отправки ────────────────────────────────────

function FailedJobsTab() {
  const [jobs, setJobs] = useState<FailedDispatchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setJobs(await getFailedDispatchJobs());
    } catch (e) {
      toast.error(errorDetail(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const retry = async (job: FailedDispatchJob) => {
    setRetrying(job.id);
    try {
      await retryDispatchJob(job.id);
      toast.success(`Отправка поставлена в очередь: ${job.tour_label}`);
      await reload();
    } catch (e) {
      toast.error(errorDetail(e));
    } finally {
      setRetrying(null);
    }
  };

  return (
    <div className={CARD}>
      <p className="mb-4 text-sm text-[#6B5435]">
        Отправки, которые не прошли (например, из-за неверного пароля Камкора). После исправления причины отправьте заново.
      </p>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Тур</TableHead>
              <TableHead>Турагент</TableHead>
              <TableHead>Паломников</TableHead>
              <TableHead>Ошибка</TableHead>
              <TableHead>Когда</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={6} className="text-center"><Loader2 className="inline w-4 h-4 animate-spin" /></TableCell></TableRow>
            )}
            {!loading && jobs.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-[#6B5435]">Упавших отправок нет</TableCell></TableRow>
            )}
            {!loading && jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell>{job.tour_label || "—"}</TableCell>
                <TableCell>{job.touragent || "—"}</TableCell>
                <TableCell>{job.pilgrims}</TableCell>
                <TableCell className="max-w-xs whitespace-normal text-xs text-red-700">{job.error_message}</TableCell>
                <TableCell className="text-xs">{formatDate(job.updated_at)}</TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="outline" disabled={retrying !== null} onClick={() => retry(job)}>
                    {retrying === job.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                    Отправить заново
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ── Журнал ──────────────────────────────────────────────

function AuditTab() {
  const [items, setItems] = useState<AuditItem[] | null>(null);

  useEffect(() => {
    getAuditLog()
      .then(setItems)
      .catch((e) => {
        toast.error(errorDetail(e));
        setItems([]);
      });
  }, []);

  return (
    <div className={CARD}>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Когда</TableHead>
              <TableHead>Справочник</TableHead>
              <TableHead>Действие</TableHead>
              <TableHead>Запись</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items === null && (
              <TableRow><TableCell colSpan={4} className="text-center"><Loader2 className="inline w-4 h-4 animate-spin" /></TableCell></TableRow>
            )}
            {items?.length === 0 && (
              <TableRow><TableCell colSpan={4} className="text-center text-[#6B5435]">Изменений пока нет</TableCell></TableRow>
            )}
            {items?.map((item) => {
              const config = ENTITIES[item.entity];
              const record = item.after || item.before || {};
              return (
                <TableRow key={item.id}>
                  <TableCell className="text-xs">{formatDate(item.created_at)}</TableCell>
                  <TableCell>{config?.tab || item.entity}</TableCell>
                  <TableCell>{ACTION_LABELS[item.action] || item.action}</TableCell>
                  <TableCell>{config ? config.title(record) : item.entity_id}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ── Страница ────────────────────────────────────────────

export function Settings() {
  return (
    <div className="p-4 md:p-12">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl mb-2 text-[#2B2318]">Настройки</h1>
            <p className="text-[#6B5435]">Справочники для создания тур-кодов. Новые значения проверяются на Камкоре.</p>
          </div>
        </div>

        <Tabs defaultValue="airlines">
          <TabsList className="mb-4 flex h-auto flex-wrap justify-start">
            {ENTITY_ORDER.map((entity) => (
              <TabsTrigger key={entity} value={entity}>{ENTITIES[entity].tab}</TabsTrigger>
            ))}
            <TabsTrigger value="kamkor">Камкор</TabsTrigger>
            <TabsTrigger value="failed">Упавшие отправки</TabsTrigger>
            <TabsTrigger value="audit">Журнал</TabsTrigger>
          </TabsList>
          {ENTITY_ORDER.map((entity) => (
            <TabsContent key={entity} value={entity}>
              <EntityTab entity={entity} />
            </TabsContent>
          ))}
          <TabsContent value="kamkor"><KamkorTab /></TabsContent>
          <TabsContent value="failed"><FailedJobsTab /></TabsContent>
          <TabsContent value="audit"><AuditTab /></TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
