import { useEffect, useMemo, useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Search, Plus } from "lucide-react";
import {
  addTourPackagePilgrim,
  ComparePilgrimRow,
  enqueueTourPackageSingle,
  getTourPackage,
  listTourPackages,
  MatchedPilgrimRow,
  TourPackageDetailResponse,
  TourPackageSummary,
} from "../../src/lib/api/tourPackages";
import { getDispatchJob } from "../../src/lib/api/dispatch";

const toIsoDate = (dateValue: string): string => {
  const parts = dateValue.split(".");
  if (parts.length !== 3) return "";
  const [dd, mm, yyyy] = parts;
  if (!dd || !mm || !yyyy) return "";
  return `${yyyy}-${mm}-${dd}`;
};

const normalizeDocument = (value?: string) => {
  const cleaned = (value || "").toUpperCase().replace(/[^0-9A-ZА-ЯЁ_]/g, "");
  if (!cleaned) return "";
  const digits = cleaned.replace(/\D/g, "");
  if (!digits || !digits.startsWith("1")) return "";
  return cleaned;
};

const normalizeNameValue = (value?: string) =>
  (value || "").trim().toUpperCase();

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type EditableField = "surname" | "name" | "document";
type EditableTable = "sheet" | "manifest";
type EditingCell = {
  table: EditableTable;
  rowIndex: number;
  field: EditableField;
  value: string;
};

type PendingCreateTarget = {
  table: EditableTable | "manual";
  rowIndex?: number;
};

export function TourPackages() {
  const [tourPackages, setTourPackages] = useState<TourPackageSummary[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [selectedPackageDetail, setSelectedPackageDetail] = useState<TourPackageDetailResponse | null>(null);
  const [matchedRows, setMatchedRows] = useState<MatchedPilgrimRow[]>([]);
  const [sheetOnlyRows, setSheetOnlyRows] = useState<ComparePilgrimRow[]>([]);
  const [manifestOnlyRows, setManifestOnlyRows] = useState<ComparePilgrimRow[]>([]);

  const [searchDate, setSearchDate] = useState("");
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [pendingCreateTarget, setPendingCreateTarget] = useState<PendingCreateTarget | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInfo, setActionInfo] = useState<string | null>(null);

  const [isManualCreateOpen, setIsManualCreateOpen] = useState(false);
  const [manualSurname, setManualSurname] = useState("");
  const [manualDocument, setManualDocument] = useState("");

  const loadTourPackages = async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      const response = await listTourPackages();
      const items = Array.isArray(response?.items) ? response.items : [];
      setTourPackages(items);
    } catch (e) {
      console.error("Error loading tour packages:", e);
      setTourPackages([]);
      setError("Не удалось загрузить список туров");
    } finally {
      setIsLoadingList(false);
    }
  };

  const loadTourPackageDetail = async (tourId: string) => {
    setIsLoadingDetail(true);
    setError(null);
    try {
      const response = await getTourPackage(tourId);
      setSelectedPackageDetail(response);
      setMatchedRows(response.matched || []);
      setSheetOnlyRows(response.in_sheet_not_in_manifest || []);
      setManifestOnlyRows(response.in_manifest_not_in_sheet || []);
      setActionError(null);
      setActionInfo(null);
      setEditingCell(null);
      setPendingCreateTarget(null);
    } catch (e) {
      console.error("Error loading tour package detail:", e);
      setSelectedPackageDetail(null);
      setMatchedRows([]);
      setSheetOnlyRows([]);
      setManifestOnlyRows([]);
      setError("Не удалось загрузить данные тура");
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    loadTourPackages();
  }, []);

  const filteredPackages = useMemo<TourPackageSummary[]>(() => {
    const source = Array.isArray(tourPackages) ? tourPackages : [];
    if (!searchDate) return source;
    return source.filter((pkg) => {
      const startIso = toIsoDate(pkg.date_start);
      const endIso = toIsoDate(pkg.date_end);
      return startIso.includes(searchDate) || endIso.includes(searchDate);
    });
  }, [searchDate, tourPackages]);

  useEffect(() => {
    if (!selectedPackageId) return;
    setTourPackages((prev) =>
      prev.map((pkg) =>
        pkg.id === selectedPackageId
          ? { ...pkg, pilgrims_count: matchedRows.length }
          : pkg
      )
    );
  }, [matchedRows.length, selectedPackageId]);

  const handleSelectPackage = async (tourId: string) => {
    setSelectedPackageId(tourId);
    setSelectedPackageDetail(null);
    await loadTourPackageDetail(tourId);
  };

  const beginEditCell = (
    table: EditableTable,
    rowIndex: number,
    field: EditableField,
    value: string
  ) => {
    setEditingCell({
      table,
      rowIndex,
      field,
      value: value || "",
    });
  };

  const commitEditCell = () => {
    if (!editingCell) return;

    const normalizedValue =
      editingCell.field === "document"
        ? normalizeDocument(editingCell.value)
        : normalizeNameValue(editingCell.value);

    if (editingCell.table === "sheet") {
      setSheetOnlyRows((prev) =>
        prev.map((row, index) =>
          index === editingCell.rowIndex
            ? { ...row, [editingCell.field]: normalizedValue }
            : row
        )
      );
    } else {
      setManifestOnlyRows((prev) =>
        prev.map((row, index) =>
          index === editingCell.rowIndex
            ? { ...row, [editingCell.field]: normalizedValue }
            : row
        )
      );
    }

    setEditingCell(null);
  };

  const cancelEditCell = () => {
    setEditingCell(null);
  };

  const renderEditableCell = (
    table: EditableTable,
    rowIndex: number,
    field: EditableField,
    value: string,
    textClassName: string
  ) => {
    const isEditing =
      editingCell?.table === table &&
      editingCell?.rowIndex === rowIndex &&
      editingCell?.field === field;

    if (isEditing && editingCell) {
      return (
        <Input
          autoFocus
          value={editingCell.value}
          onChange={(event) =>
            setEditingCell((prev) => (prev ? { ...prev, value: event.target.value } : prev))
          }
          onBlur={commitEditCell}
          onKeyDown={(event) => {
            if (event.key === "Enter") commitEditCell();
            if (event.key === "Escape") cancelEditCell();
          }}
          className="h-8 bg-white border-[#E5DDD0] focus:border-[#B8985F]"
        />
      );
    }

    return (
      <button
        type="button"
        className={`${textClassName} text-left w-full`}
        onDoubleClick={() => beginEditCell(table, rowIndex, field, value)}
        title="Двойной клик для редактирования"
      >
        {value || "-"}
      </button>
    );
  };

  const waitForDispatchCompletion = async (jobId: string) => {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const snapshot = await getDispatchJob(jobId);
      const status = (snapshot.status || "").toLowerCase();
      if (status === "sent") {
        return { ok: true as const };
      }
      if (status === "failed") {
        return {
          ok: false as const,
          error: snapshot.error_message || "Задача завершилась ошибкой",
        };
      }
      await sleep(1200);
    }

    return {
      ok: false as const,
      error: "Превышено время ожидания результата очереди",
    };
  };

  const appendMatchedRow = (row: MatchedPilgrimRow) => {
    setMatchedRows((prev) => {
      const normalizedDoc = normalizeDocument(row.document);
      const existingIndex = prev.findIndex((p) => {
        if (normalizeDocument(p.document) && normalizedDoc) {
          return normalizeDocument(p.document) === normalizedDoc;
        }
        return (
          normalizeNameValue(p.surname) === normalizeNameValue(row.surname) &&
          normalizeNameValue(p.name) === normalizeNameValue(row.name)
        );
      });

      if (existingIndex >= 0) {
        return prev.map((item, index) =>
          index === existingIndex
            ? {
                ...item,
                ...row,
                surname: row.surname || item.surname,
                name: row.name || item.name,
                document: row.document || item.document,
                package_name: row.package_name || item.package_name,
                tour_code: row.tour_code || item.tour_code,
              }
            : item
        );
      }

      return [...prev, row];
    });
  };

  const createSingleAndPersist = async (
    source: PendingCreateTarget,
    row: ComparePilgrimRow
  ): Promise<boolean> => {
    if (!selectedPackageId || !selectedPackageDetail) {
      setActionError("Сначала выберите тур");
      return false;
    }

    const surname = normalizeNameValue(row.surname);
    const name = normalizeNameValue(row.name);
    const document = normalizeDocument(row.document);
    if (!surname) {
      setActionError("Фамилия обязательна");
      return false;
    }
    if (!document) {
      setActionError("Паспорт обязателен");
      return false;
    }

    setPendingCreateTarget(source);
    setActionError(null);
    setActionInfo(null);

    try {
      const enqueueResponse = await enqueueTourPackageSingle(selectedPackageId, {
        person: {
          surname,
          name,
          document,
          package_name: row.package_name || "",
          tour_name: row.tour_name || selectedPackageDetail.sheet_name || "",
        },
        dispatch_overrides: {
          filialid: selectedPackageDetail.dispatch_overrides?.filialid || "",
          firmid: selectedPackageDetail.dispatch_overrides?.firmid || "",
          firmname: selectedPackageDetail.dispatch_overrides?.firmname || "",
          q_touragent: selectedPackageDetail.dispatch_overrides?.q_touragent || "",
          q_touragent_bin: selectedPackageDetail.dispatch_overrides?.q_touragent_bin || "",
        },
      });

      const completed = await waitForDispatchCompletion(enqueueResponse.id);
      if (!completed.ok) {
        throw new Error(completed.error);
      }

      const added = await addTourPackagePilgrim(selectedPackageId, {
        full_name: `${surname} ${name || "-"}`.trim(),
        document,
        package_name: row.package_name || "",
      });

      appendMatchedRow(added);

      if (source.table === "sheet" && typeof source.rowIndex === "number") {
        setSheetOnlyRows((prev) => prev.filter((_, index) => index !== source.rowIndex));
      }
      if (source.table === "manifest" && typeof source.rowIndex === "number") {
        setManifestOnlyRows((prev) => prev.filter((_, index) => index !== source.rowIndex));
      }

      setActionInfo(`Успешно отправлено: ${surname} ${name}`.trim());
      return true;
    } catch (e) {
      console.error("Single dispatch failed:", e);
      setActionError(e instanceof Error ? e.message : "Не удалось создать тур код");
      return false;
    } finally {
      setPendingCreateTarget(null);
    }
  };

  const handleCreateFromSheet = async (index: number) => {
    const row = sheetOnlyRows[index];
    if (!row) return;
    await createSingleAndPersist({ table: "sheet", rowIndex: index }, row);
  };

  const handleCreateFromManifest = async (index: number) => {
    const row = manifestOnlyRows[index];
    if (!row) return;
    await createSingleAndPersist({ table: "manifest", rowIndex: index }, row);
  };

  const handleManualCreate = async () => {
    const row: ComparePilgrimRow = {
      surname: manualSurname,
      name: "",
      document: manualDocument,
      package_name: "",
      tour_name: selectedPackageDetail?.sheet_name || "",
    };

    const ok = await createSingleAndPersist({ table: "manual" }, row);
    if (ok) {
      setManualSurname("");
      setManualDocument("");
      setIsManualCreateOpen(false);
    }
  };

  const matchedCount = matchedRows.length;
  const inSheetOnlyCount = sheetOnlyRows.length;
  const inManifestOnlyCount = manifestOnlyRows.length;

  return (
    <div className="p-12">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl mb-2 text-[#2B2318]">Пакеты с тур кодом</h1>
          <p className="text-[#6B5435]">Просмотр и управление туристическими пакетами</p>
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-4">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
              <h2 className="mb-4 text-[#2B2318]">Список туров</h2>

              <div className="mb-4 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8B6F47]" />
                <Input
                  type="date"
                  value={searchDate}
                  onChange={(e) => setSearchDate(e.target.value)}
                  placeholder="Поиск по дате"
                  className="pl-10 bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>

              <div className="space-y-2">
                {isLoadingList ? (
                  <p className="text-sm text-[#6B5435]">Загрузка...</p>
                ) : filteredPackages.length === 0 ? (
                  <p className="text-sm text-[#8B6F47]">Туры не найдены</p>
                ) : (
                  filteredPackages.map((pkg) => (
                    <button
                      key={pkg.id}
                      onClick={() => handleSelectPackage(pkg.id)}
                      className={`
                        w-full text-left p-4 rounded-lg transition-all duration-200 border
                        ${
                          selectedPackageId === pkg.id
                            ? "bg-gradient-to-r from-[#B8985F] to-[#A88952] text-white border-[#B8985F] shadow-md"
                            : "bg-[#F5F1EA] border-[#E5DDD0] hover:border-[#B8985F] text-[#2B2318]"
                        }
                      `}
                    >
                      <div className="flex justify-between items-start mb-1">
                        <p className="text-sm opacity-90">
                          {pkg.date_start} - {pkg.date_end}
                        </p>
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            selectedPackageId === pkg.id
                              ? "bg-white/20"
                              : "bg-[#B8985F]/10 text-[#8B6F47]"
                          }`}
                        >
                          {pkg.pilgrims_count} чел.
                        </span>
                      </div>
                      <p>{pkg.sheet_name || pkg.route || "Тур"}</p>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="col-span-8">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-[#2B2318]">
                  {selectedPackageDetail
                    ? `Тур ${selectedPackageDetail.sheet_name || selectedPackageDetail.route}`
                    : "Выберите тур"}
                </h2>
                {selectedPackageDetail && (
                  <Button
                    className="bg-gradient-to-r from-[#B8985F] to-[#A88952] hover:from-[#A88952] hover:to-[#8B6F47] text-white"
                    onClick={() => {
                      setIsManualCreateOpen(true);
                      setActionError(null);
                    }}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Создать
                  </Button>
                )}
              </div>

              {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
              {actionError && <p className="mb-4 text-sm text-red-600">{actionError}</p>}
              {actionInfo && <p className="mb-4 text-sm text-green-700">{actionInfo}</p>}

              {selectedPackageId ? (
                isLoadingDetail ? (
                  <div className="flex items-center justify-center h-64 text-[#8B6F47]">
                    <p>Загрузка данных тура...</p>
                  </div>
                ) : !selectedPackageDetail ? (
                  <div className="flex items-center justify-center h-64 text-[#8B6F47]">
                    <p>Не удалось загрузить тур</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="p-4 bg-[#F5F1EA] border border-[#E5DDD0] rounded-lg text-sm text-[#6B5435]">
                      <p>Таблица: {selectedPackageDetail.spreadsheet_name || "-"}</p>
                      <p>Лист: {selectedPackageDetail.sheet_name || "-"}</p>
                      <p>Маршрут: {selectedPackageDetail.route || "-"}</p>
                      <p>Период: {selectedPackageDetail.date_start} - {selectedPackageDetail.date_end}</p>
                      <p>Дней: {selectedPackageDetail.days || "-"}</p>
                      <p>Город вылета: {selectedPackageDetail.departure_city || "-"}</p>
                      <p>Страна: {selectedPackageDetail.country || "-"}</p>
                      <p>Отель: {selectedPackageDetail.hotel || "-"}</p>
                      <p>Комментарий: {selectedPackageDetail.remark || "-"}</p>
                      <p>Манифест: {selectedPackageDetail.manifest_filename || "-"}</p>
                    </div>

                    <div className="mb-2 grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="bg-green-50 p-3 rounded-lg border border-green-200 text-center">
                        <p className="text-2xl font-bold text-green-700">{matchedCount}</p>
                        <p className="text-xs text-green-600">Совпадения</p>
                      </div>
                      <div className="bg-orange-50 p-3 rounded-lg border border-orange-200 text-center">
                        <p className="text-2xl font-bold text-orange-700">{inSheetOnlyCount}</p>
                        <p className="text-xs text-orange-600">В таблице, нет в манифесте</p>
                      </div>
                      <div className="bg-red-50 p-3 rounded-lg border border-red-200 text-center">
                        <p className="text-2xl font-bold text-red-700">{inManifestOnlyCount}</p>
                        <p className="text-xs text-red-600">В манифесте, нет в таблице</p>
                      </div>
                    </div>

                    <div>
                      <h4 className="mb-2 text-[#2B2318] font-medium">Совпадения ({matchedCount})</h4>
                      <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-green-50 hover:bg-green-50">
                              <TableHead className="w-12">№</TableHead>
                              <TableHead>Фамилия</TableHead>
                              <TableHead>Имя</TableHead>
                              <TableHead>Паспорт</TableHead>
                              <TableHead>Пакет</TableHead>
                              <TableHead>Тур код</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {matchedRows.map((row, idx) => (
                              <TableRow key={row.id}>
                                <TableCell>{idx + 1}</TableCell>
                                <TableCell>{row.surname}</TableCell>
                                <TableCell>{row.name || "-"}</TableCell>
                                <TableCell>{row.document || "-"}</TableCell>
                                <TableCell>{row.package_name || "-"}</TableCell>
                                <TableCell>{row.tour_code || "-"}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>

                    {inSheetOnlyCount > 0 && (
                      <div>
                        <h4 className="mb-2 text-[#2B2318] font-medium">
                          В таблице, нет в манифесте ({inSheetOnlyCount})
                        </h4>
                        <div className="border border-[#FFD4A3] rounded-lg overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow className="bg-[#FFF4E6] hover:bg-[#FFF4E6]">
                                <TableHead className="w-12">№</TableHead>
                                <TableHead>Фамилия</TableHead>
                                <TableHead>Имя</TableHead>
                                <TableHead>Паспорт</TableHead>
                                <TableHead>Пакет</TableHead>
                                <TableHead>Тур код</TableHead>
                                <TableHead>Создать</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {sheetOnlyRows.map((row, idx) => {
                                const isPending =
                                  pendingCreateTarget?.table === "sheet" &&
                                  pendingCreateTarget?.rowIndex === idx;
                                const hasDocument = Boolean(normalizeDocument(row.document));
                                const hasSurname = Boolean(normalizeNameValue(row.surname));
                                return (
                                  <TableRow key={`${row.surname}-${row.name}-${row.document}-${idx}`}>
                                    <TableCell>{idx + 1}</TableCell>
                                    <TableCell>
                                      {renderEditableCell("sheet", idx, "surname", row.surname, "text-[#2B2318]")}
                                    </TableCell>
                                    <TableCell>
                                      {renderEditableCell("sheet", idx, "name", row.name, "text-[#2B2318]")}
                                    </TableCell>
                                    <TableCell>
                                      {renderEditableCell("sheet", idx, "document", row.document || "", "text-[#6B5435]")}
                                    </TableCell>
                                    <TableCell>{row.package_name || "-"}</TableCell>
                                    <TableCell>
                                      {hasDocument ? "-" : "Нет паспорта (ожидает)"}
                                    </TableCell>
                                    <TableCell>
                                      {hasDocument && hasSurname ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                                          disabled={Boolean(pendingCreateTarget)}
                                          onClick={() => handleCreateFromSheet(idx)}
                                        >
                                          {isPending ? "Отправка..." : "Создать"}
                                        </Button>
                                      ) : (
                                        <span className="text-[#6B5435]">-</span>
                                      )}
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    )}

                    {inManifestOnlyCount > 0 && (
                      <div>
                        <h4 className="mb-2 text-[#2B2318] font-medium">
                          В манифесте, нет в таблице ({inManifestOnlyCount})
                        </h4>
                        <div className="border border-red-200 rounded-lg overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow className="bg-red-50 hover:bg-red-50">
                                <TableHead className="w-12">№</TableHead>
                                <TableHead>Фамилия</TableHead>
                                <TableHead>Имя</TableHead>
                                <TableHead>Паспорт</TableHead>
                                <TableHead>Пакет</TableHead>
                                <TableHead>Тур код</TableHead>
                                <TableHead>Создать</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {manifestOnlyRows.map((row, idx) => {
                                const isPending =
                                  pendingCreateTarget?.table === "manifest" &&
                                  pendingCreateTarget?.rowIndex === idx;
                                const hasDocument = Boolean(normalizeDocument(row.document));
                                const hasSurname = Boolean(normalizeNameValue(row.surname));
                                return (
                                  <TableRow key={`${row.surname}-${row.name}-${row.document}-${idx}`}>
                                    <TableCell>{idx + 1}</TableCell>
                                    <TableCell>
                                      {renderEditableCell("manifest", idx, "surname", row.surname, "text-[#2B2318]")}
                                    </TableCell>
                                    <TableCell>
                                      {renderEditableCell("manifest", idx, "name", row.name, "text-[#2B2318]")}
                                    </TableCell>
                                    <TableCell>
                                      {renderEditableCell("manifest", idx, "document", row.document || "", "text-[#6B5435]")}
                                    </TableCell>
                                    <TableCell>{row.package_name || "-"}</TableCell>
                                    <TableCell>
                                      {hasDocument ? "-" : "Нет паспорта (ожидает)"}
                                    </TableCell>
                                    <TableCell>
                                      {hasDocument && hasSurname ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                                          disabled={Boolean(pendingCreateTarget)}
                                          onClick={() => handleCreateFromManifest(idx)}
                                        >
                                          {isPending ? "Отправка..." : "Создать"}
                                        </Button>
                                      ) : (
                                        <span className="text-[#6B5435]">-</span>
                                      )}
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    )}
                  </div>
                )
              ) : (
                <div className="flex items-center justify-center h-64 text-[#8B6F47]">
                  <p>Выберите тур из списка слева для просмотра паломников</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {isManualCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-xl border border-[#E5DDD0] bg-white p-5 shadow-2xl">
            <h4 className="text-[#2B2318] font-medium mb-4">Создать тур код вручную</h4>
            <div className="space-y-3">
              <div>
                <label className="block mb-1 text-sm text-[#2B2318]">Фамилия</label>
                <Input
                  value={manualSurname}
                  onChange={(e) => setManualSurname(e.target.value)}
                  className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
              <div>
                <label className="block mb-1 text-sm text-[#2B2318]">Паспорт</label>
                <Input
                  value={manualDocument}
                  onChange={(e) => setManualDocument(e.target.value)}
                  className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Button
                type="button"
                className="w-full sm:w-[230px] bg-gradient-to-r from-[#5E8C6B] to-[#4F7B5C] hover:from-[#4F7B5C] hover:to-[#446A50] text-white shadow-sm"
                disabled={
                  Boolean(pendingCreateTarget) ||
                  !normalizeNameValue(manualSurname) ||
                  !normalizeDocument(manualDocument)
                }
                onClick={handleManualCreate}
              >
                {pendingCreateTarget?.table === "manual" ? "Отправка..." : "Подтвердить создание тур кода"}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full sm:w-[230px] border-[#D8CCB8] bg-white text-[#6B5435] hover:bg-[#F5F1EA]"
                disabled={Boolean(pendingCreateTarget)}
                onClick={() => {
                  setIsManualCreateOpen(false);
                  setManualSurname("");
                  setManualDocument("");
                }}
              >
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
