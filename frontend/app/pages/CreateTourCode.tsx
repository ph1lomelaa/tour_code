import { useEffect, useState } from "react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Calendar, Clock, MapPin, Building, Upload, Plus } from "lucide-react";
import { searchToursByDate, getSheetPilgrims, TourOption, PilgrimInPackage } from "../../src/lib/api/tours";
import { uploadManifest, Pilgrim } from "../../src/lib/api/manifest";
import { enqueueDispatchJob } from "../../src/lib/api/dispatch";
import { getTourPackage } from "../../src/lib/api/tourPackages";
import { useSearchParams } from "react-router";

// Список отелей
const hotels = [
  "Hilton Makkah Convention Hotel",
  "Swissotel Makkah",
  "Pullman ZamZam Makkah",
  "Fairmont Makkah Clock Royal Tower",
  "Conrad Makkah",
  "Anjum Hotel Makkah",
  "Elaf Kinda Hotel",
  "Millennium Al Aqeeq Hotel",
];

// Паломник с привязкой к пакету
type PilgrimWithPackage = PilgrimInPackage & { package_name: string; tour_name: string };
type ManifestPilgrimWithPackage = Pilgrim & { package_name?: string; tour_name?: string; tour_code?: string };
type MatchedOriginTable = "sheet" | "manifest";
type MatchedPilgrim = Pilgrim & {
  package_name: string;
  tour_name: string;
  tour_code?: string;
  _sourceTable?: MatchedOriginTable;
};
type MatchedEditableField = "surname" | "name" | "document" | "package_name" | "tour_name";
type MatchedEditorState = {
  index: number;
  draft: MatchedPilgrim;
};

type EditableField = "surname" | "name" | "document";
type EditableTable = "sheet" | "manifest";
type EditingCell = {
  table: EditableTable;
  rowIndex: number;
  field: EditableField;
  value: string;
};

type ComparablePilgrim = {
  surname?: string;
  name?: string;
  document?: string;
  iin?: string;
};

const normalizeDocument = (value?: string) =>
  (value || "").toUpperCase().replace(/[^0-9A-ZА-ЯЁ_]/g, "");

const normalizeIin = (value?: string) =>
  (value || "").replace(/\D/g, "");

const normalizeNamePart = (value?: string) =>
  (value || "").toUpperCase().replace(/[^A-ZА-ЯЁ]/g, "");

const buildMatchKeys = (pilgrim: ComparablePilgrim): string[] => {
  const keys: string[] = [];

  const doc = normalizeDocument(pilgrim.document);
  if (doc) {
    keys.push(`DOC:${doc}`);
  }

  const iin = normalizeIin(pilgrim.iin);
  if (iin) {
    keys.push(`IIN:${iin}`);
  }

  const surname = normalizeNamePart(pilgrim.surname);
  const name = normalizeNamePart(pilgrim.name);
  if (surname && name) {
    keys.push(`NAME:${surname}|${name}`);
  }

  return keys;
};

const levenshteinDistance = (a: string, b: string): number => {
  if (a === b) return 0;
  if (!a) return b.length;
  if (!b) return a.length;

  const rows = a.length + 1;
  const cols = b.length + 1;
  const matrix: number[][] = Array.from({ length: rows }, () => Array(cols).fill(0));

  for (let i = 0; i < rows; i += 1) matrix[i][0] = i;
  for (let j = 0; j < cols; j += 1) matrix[0][j] = j;

  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      );
    }
  }

  return matrix[a.length][b.length];
};

const isSingleAdjacentTransposition = (a: string, b: string): boolean => {
  if (!a || !b || a.length !== b.length) return false;

  let firstDiff = -1;
  let secondDiff = -1;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] === b[i]) continue;
    if (firstDiff === -1) {
      firstDiff = i;
      continue;
    }
    if (secondDiff === -1) {
      secondDiff = i;
      continue;
    }
    return false;
  }

  if (firstDiff === -1 || secondDiff === -1) return false;
  if (secondDiff !== firstDiff + 1) return false;

  return (
    a[firstDiff] === b[secondDiff] &&
    a[secondDiff] === b[firstDiff]
  );
};

const nameDistanceScore = (a: string, b: string): number => {
  if (a === b) return 0;
  const distance = levenshteinDistance(a, b);
  if (isSingleAdjacentTransposition(a, b)) {
    return Math.min(distance, 1);
  }
  return distance;
};

const isPassportSimilar = (sheetDocument?: string, manifestDocument?: string): boolean => {
  const sheetDoc = normalizeDocument(sheetDocument);
  const manifestDoc = normalizeDocument(manifestDocument);

  if (!sheetDoc || !manifestDoc) {
    return false;
  }

  if (sheetDoc === manifestDoc) {
    return true;
  }

  const sheetDigits = sheetDoc.replace(/\D/g, "");
  const manifestDigits = manifestDoc.replace(/\D/g, "");
  if (sheetDigits && manifestDigits) {
    if (sheetDigits === manifestDigits) {
      return true;
    }
    const digitsDistance = levenshteinDistance(sheetDigits, manifestDigits);
    if (digitsDistance <= 1 && Math.abs(sheetDigits.length - manifestDigits.length) <= 1) {
      return true;
    }
  }

  const fullDistance = levenshteinDistance(sheetDoc, manifestDoc);
  return fullDistance <= 2 && Math.abs(sheetDoc.length - manifestDoc.length) <= 1;
};

const dedupeManifestPilgrims = (pilgrims: Pilgrim[]): Pilgrim[] => {
  const seen = new Set<string>();
  const unique: Pilgrim[] = [];

  for (const pilgrim of pilgrims) {
    const doc = normalizeDocument(pilgrim.document);
    const iin = normalizeIin(pilgrim.iin);
    const surname = normalizeNamePart(pilgrim.surname);
    const name = normalizeNamePart(pilgrim.name);

    const key = doc
      ? `DOC:${doc}`
      : iin
        ? `IIN:${iin}`
        : surname && name
          ? `NAME:${surname}|${name}`
          : `RAW:${pilgrim.surname}|${pilgrim.name}|${pilgrim.document || ""}|${pilgrim.iin || ""}`;

    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(pilgrim);
  }

  return unique;
};

const findFuzzyManifestMatchIndex = (
  sheetPilgrim: PilgrimWithPackage,
  manifestPilgrims: Pilgrim[],
  matchedManifestIndexes: Set<number>
): number | null => {
  const sheetSurname = normalizeNamePart(sheetPilgrim.surname);
  const sheetName = normalizeNamePart(sheetPilgrim.name);
  const sheetDoc = normalizeDocument(sheetPilgrim.document);

  if (!sheetSurname || !sheetName) {
    return null;
  }

  let bestIndex: number | null = null;
  let bestScore = Number.POSITIVE_INFINITY;

  for (let index = 0; index < manifestPilgrims.length; index += 1) {
    if (matchedManifestIndexes.has(index)) continue;

    const manifestPilgrim = manifestPilgrims[index];
    const manifestSurname = normalizeNamePart(manifestPilgrim.surname);
    const manifestName = normalizeNamePart(manifestPilgrim.name);
    const manifestDoc = normalizeDocument(manifestPilgrim.document);

    if (!manifestSurname || !manifestName) continue;
    if (sheetSurname[0] !== manifestSurname[0] || sheetName[0] !== manifestName[0]) continue;

    const surnameDistance = nameDistanceScore(sheetSurname, manifestSurname);
    const nameDistance = nameDistanceScore(sheetName, manifestName);

    if (surnameDistance > 1 || nameDistance > 2) continue;

    // Если в обеих записях есть паспорт, он тоже должен быть похож.
    if (sheetDoc && manifestDoc && !isPassportSimilar(sheetDoc, manifestDoc)) {
      continue;
    }

    // Если паспорт есть только в таблице, а в манифесте пусто, считаем это ненадёжным матчем.
    if (sheetDoc && !manifestDoc) {
      continue;
    }

    const score = surnameDistance * 2 + nameDistance + (sheetDoc ? 0 : 1);
    if (score < bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  }

  // Ограничиваем слишком слабые нестрогие матчи.
  if (bestIndex === null || bestScore > 4) {
    return null;
  }

  return bestIndex;
};

const findPassportDrivenManifestMatchIndex = (
  sheetPilgrim: PilgrimWithPackage,
  manifestPilgrims: Pilgrim[],
  matchedManifestIndexes: Set<number>
): number | null => {
  const sheetDoc = normalizeDocument(sheetPilgrim.document);
  if (!sheetDoc) {
    return null;
  }

  const sheetSurname = normalizeNamePart(sheetPilgrim.surname);
  const sheetName = normalizeNamePart(sheetPilgrim.name);
  const candidates: Array<{ index: number; score: number }> = [];

  for (let index = 0; index < manifestPilgrims.length; index += 1) {
    if (matchedManifestIndexes.has(index)) continue;

    const manifestPilgrim = manifestPilgrims[index];
    const manifestDoc = normalizeDocument(manifestPilgrim.document);
    if (!manifestDoc || !isPassportSimilar(sheetDoc, manifestDoc)) continue;

    const manifestSurname = normalizeNamePart(manifestPilgrim.surname);
    const manifestName = normalizeNamePart(manifestPilgrim.name);
    const surnameDistance =
      sheetSurname && manifestSurname ? nameDistanceScore(sheetSurname, manifestSurname) : 0;
    const nameDistance =
      sheetName && manifestName ? nameDistanceScore(sheetName, manifestName) : 0;

    // Если паспорт похож, допускаем более мягкое сравнение ФИО, но отсекаем явно чужие записи.
    if ((sheetSurname && manifestSurname && surnameDistance > 3) || (sheetName && manifestName && nameDistance > 3)) {
      continue;
    }

    candidates.push({
      index,
      score: surnameDistance * 2 + nameDistance,
    });
  }

  if (candidates.length === 0) {
    return null;
  }

  candidates.sort((a, b) => a.score - b.score);

  if (candidates.length > 1 && candidates[0].score === candidates[1].score && candidates[0].score > 0) {
    return null;
  }

  return candidates[0].index;
};

export function CreateTourCode() {
  const [searchParams] = useSearchParams();
  const prefilledTourId = searchParams.get("tourId");

  const [selectedDateShort, setSelectedDateShort] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [days, setDays] = useState(0);
  const [availableFlights, setAvailableFlights] = useState<string[]>([]);
  const [selectedFlight, setSelectedFlight] = useState("");
  const [selectedCountry, setSelectedCountry] = useState("Саудовская Аравия");
  const [selectedHotel, setSelectedHotel] = useState("");
  const [dispatchTouragentName, setDispatchTouragentName] = useState("HICKMET PREMIUM");
  const [dispatchTouragentBin, setDispatchTouragentBin] = useState("240340000277");

  // Tour search
  const [tourOptions, setTourOptions] = useState<TourOption[]>([]);
  const [isLoadingTours, setIsLoadingTours] = useState(false);
  const [tourSearchError, setTourSearchError] = useState<string | null>(null);
  const [dateInput, setDateInput] = useState("");
  const [selectedTour, setSelectedTour] = useState<TourOption | null>(null);

  // Manifest
  const [manifestFile, setManifestFile] = useState<File | null>(null);
  const [manifestPilgrims, setManifestPilgrims] = useState<Pilgrim[]>([]);
  const [isUploadingManifest, setIsUploadingManifest] = useState(false);
  const [manifestError, setManifestError] = useState<string | null>(null);

  // Flat comparison results
  const [allMatched, setAllMatched] = useState<MatchedPilgrim[]>([]);
  const [allInSheetNotManifest, setAllInSheetNotManifest] = useState<PilgrimWithPackage[]>([]);
  const [allInManifestNotSheet, setAllInManifestNotSheet] = useState<ManifestPilgrimWithPackage[]>([]);
  const [isComparing, setIsComparing] = useState(false);
  const [isQueueingDispatch, setIsQueueingDispatch] = useState(false);
  const [dispatchInfo, setDispatchInfo] = useState<string | null>(null);
  const [isPrefillingFromPackage, setIsPrefillingFromPackage] = useState(false);
  const [prefillDoneForTourId, setPrefillDoneForTourId] = useState<string | null>(null);
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [matchedEditor, setMatchedEditor] = useState<MatchedEditorState | null>(null);

  // ============= Handlers =============

  const normalizeEditableValue = (field: EditableField, rawValue: string): string => {
    const value = rawValue.trim();
    if (!value) return "";
    if (field === "document") return value.toUpperCase();
    return value.toUpperCase();
  };

  const normalizeMatchedValue = (field: MatchedEditableField, rawValue: string): string => {
    const value = rawValue.trim();
    if (!value) return "";
    if (field === "surname" || field === "name" || field === "document") {
      return value.toUpperCase();
    }
    return value;
  };

  const applyHickmetPreset = () => {
    setDispatchTouragentName("HICKMET PREMIUM");
    setDispatchTouragentBin("240340000277");
  };

  const applyNiyetPreset = () => {
    setDispatchTouragentName("NIYET");
    setDispatchTouragentBin("");
  };

  const clearDispatchOverrides = () => {
    setDispatchTouragentName("");
    setDispatchTouragentBin("");
  };

  const openMatchedEditor = (index: number) => {
    const row = allMatched[index];
    if (!row) return;
    setMatchedEditor({
      index,
      draft: { ...row },
    });
  };

  const updateMatchedEditorField = (field: MatchedEditableField, value: string) => {
    setMatchedEditor((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        draft: {
          ...prev.draft,
          [field]: value,
        },
      };
    });
  };

  const saveMatchedEditor = () => {
    if (!matchedEditor) return;

    const normalizedDraft: MatchedPilgrim = {
      ...matchedEditor.draft,
      surname: normalizeMatchedValue("surname", matchedEditor.draft.surname || ""),
      name: normalizeMatchedValue("name", matchedEditor.draft.name || ""),
      document: normalizeMatchedValue("document", matchedEditor.draft.document || ""),
      package_name: normalizeMatchedValue("package_name", matchedEditor.draft.package_name || ""),
      tour_name: normalizeMatchedValue("tour_name", matchedEditor.draft.tour_name || ""),
    };

    setAllMatched((prev) =>
      prev.map((row, index) => (index === matchedEditor.index ? normalizedDraft : row))
    );
    setMatchedEditor(null);
  };

  const deleteMatchedEditorRow = () => {
    if (!matchedEditor) return;
    setAllMatched((prev) => prev.filter((_, index) => index !== matchedEditor.index));
    setMatchedEditor(null);
  };

  const returnMatchedToSource = () => {
    if (!matchedEditor) return;
    const source = matchedEditor.draft._sourceTable;
    if (!source) return;

    const row: MatchedPilgrim = {
      ...matchedEditor.draft,
      surname: normalizeMatchedValue("surname", matchedEditor.draft.surname || ""),
      name: normalizeMatchedValue("name", matchedEditor.draft.name || ""),
      document: normalizeMatchedValue("document", matchedEditor.draft.document || ""),
      package_name: normalizeMatchedValue("package_name", matchedEditor.draft.package_name || ""),
      tour_name: normalizeMatchedValue("tour_name", matchedEditor.draft.tour_name || ""),
    };

    if (source === "sheet") {
      const restoredRow: PilgrimWithPackage = {
        surname: row.surname,
        name: row.name,
        document: row.document || "",
        iin: row.iin || "",
        manager: row.manager || "",
        room_type: "",
        meal_type: "",
        package_name: row.package_name,
        tour_name: row.tour_name,
      };

      setAllInSheetNotManifest((prev) => {
        const alreadyExists = prev.some((p) =>
          normalizeNamePart(p.surname) === normalizeNamePart(restoredRow.surname) &&
          normalizeNamePart(p.name) === normalizeNamePart(restoredRow.name) &&
          normalizeDocument(p.document) === normalizeDocument(restoredRow.document) &&
          (p.package_name || "") === (restoredRow.package_name || "")
        );
        if (alreadyExists) return prev;
        return [...prev, restoredRow];
      });
    } else {
      const restoredRow: ManifestPilgrimWithPackage = {
        surname: row.surname,
        name: row.name,
        document: row.document || "",
        iin: row.iin || "",
        package_name: row.package_name || "",
        tour_name: row.tour_name || (selectedTour?.sheet_name || ""),
        tour_code: row.tour_code || "",
      };

      setAllInManifestNotSheet((prev) => {
        const alreadyExists = prev.some((p) =>
          normalizeNamePart(p.surname) === normalizeNamePart(restoredRow.surname) &&
          normalizeNamePart(p.name) === normalizeNamePart(restoredRow.name) &&
          normalizeDocument(p.document) === normalizeDocument(restoredRow.document) &&
          (p.package_name || "") === (restoredRow.package_name || "")
        );
        if (alreadyExists) return prev;
        return [...prev, restoredRow];
      });
    }

    setAllMatched((prev) => prev.filter((_, index) => index !== matchedEditor.index));
    setMatchedEditor(null);
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

    const normalizedValue = normalizeEditableValue(editingCell.field, editingCell.value);
    if (editingCell.table === "sheet") {
      setAllInSheetNotManifest((prev) =>
        prev.map((row, index) =>
          index === editingCell.rowIndex
            ? { ...row, [editingCell.field]: normalizedValue }
            : row
        )
      );
    } else {
      setAllInManifestNotSheet((prev) =>
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

  useEffect(() => {
    if (!prefilledTourId || prefillDoneForTourId === prefilledTourId) return;

    let cancelled = false;
    const prefillFromPackage = async () => {
      setIsPrefillingFromPackage(true);
      setManifestError(null);

      try {
        const detail = await getTourPackage(prefilledTourId);
        if (cancelled) return;

        const preselectedTour: TourOption = {
          spreadsheet_id: detail.spreadsheet_id || "",
          spreadsheet_name: detail.spreadsheet_name || "",
          sheet_name: detail.sheet_name || "",
          date_start: detail.date_start || "",
          date_end: detail.date_end || "",
          days: detail.days || 0,
          route: detail.route || "",
          departure_city: detail.departure_city || "",
        };

        setSelectedTour(preselectedTour);
        setSelectedDateShort(preselectedTour.date_start);
        setDateRange(`${preselectedTour.date_start} - ${preselectedTour.date_end}`);
        setDays(preselectedTour.days);
        setAvailableFlights(preselectedTour.route ? [preselectedTour.route] : []);
        setSelectedFlight(preselectedTour.route || "");
        setSelectedCountry(detail.country || "Саудовская Аравия");
        setSelectedHotel(detail.hotel || "");
        setDispatchTouragentName(detail.dispatch_overrides?.q_touragent || "");
        setDispatchTouragentBin(detail.dispatch_overrides?.q_touragent_bin || "");

        const dateParts = (detail.date_start || "").split(".");
        if (dateParts.length >= 2) {
          setDateInput(`${dateParts[0]}.${dateParts[1]}`);
        }

        const matchedFromDb: MatchedPilgrim[] = detail.matched.map((row) => ({
          surname: row.surname,
          name: row.name,
          document: row.document || "",
          iin: "",
          manager: "",
          package_name: row.package_name || "",
          tour_name: detail.sheet_name || "",
          tour_code: row.tour_code || "",
        }));
        setAllMatched(matchedFromDb);

        const inSheetFromDb: PilgrimWithPackage[] = detail.in_sheet_not_in_manifest.map((row) => ({
          surname: row.surname,
          name: row.name,
          document: row.document || "",
          iin: "",
          manager: "",
          room_type: "",
          meal_type: "",
          package_name: row.package_name || "",
          tour_name: row.tour_name || detail.sheet_name || "",
        }));
        setAllInSheetNotManifest(inSheetFromDb);

        const inManifestFromDb: ManifestPilgrimWithPackage[] = detail.in_manifest_not_in_sheet.map((row) => ({
          surname: row.surname,
          name: row.name,
          document: row.document || "",
          iin: "",
          package_name: row.package_name || "",
          tour_name: row.tour_name || detail.sheet_name || "",
        }));
        setAllInManifestNotSheet(inManifestFromDb);
        setDispatchInfo(null);
        setPrefillDoneForTourId(prefilledTourId);
      } catch (error) {
        if (!cancelled) {
          console.error("Error prefilling from package:", error);
          setManifestError("Не удалось загрузить данные тура для автозаполнения");
        }
      } finally {
        if (!cancelled) setIsPrefillingFromPackage(false);
      }
    };

    prefillFromPackage();
    return () => {
      cancelled = true;
    };
  }, [prefilledTourId, prefillDoneForTourId]);

  const handleSearchTours = async () => {
    if (!dateInput || dateInput.length < 4) {
      setTourSearchError("Введите дату в формате ДД.ММ (например, 17.02)");
      return;
    }

    setIsLoadingTours(true);
    setTourSearchError(null);
    setTourOptions([]);

    try {
      const response = await searchToursByDate(dateInput);

      if (response.success && response.tours.length > 0) {
        setTourOptions(response.tours);
      } else {
        setTourSearchError("Туры на эту дату не найдены");
      }
    } catch (error) {
      console.error("Error searching tours:", error);
      setTourSearchError("Ошибка при поиске туров. Проверьте подключение к серверу.");
    } finally {
      setIsLoadingTours(false);
    }
  };

  const handleTourSelect = (tour: TourOption) => {
    setSelectedTour(tour);
    setSelectedDateShort(tour.date_start);
    setDateRange(`${tour.date_start} - ${tour.date_end}`);
    setDays(tour.days);
    setAvailableFlights([tour.route]);
    setSelectedFlight(tour.route);

    // Сбрасываем результаты при выборе нового тура
    setAllMatched([]);
    setAllInSheetNotManifest([]);
    setAllInManifestNotSheet([]);
    setDispatchInfo(null);
  };

  const handleManifestUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setManifestFile(file);
    setIsUploadingManifest(true);
    setManifestError(null);
    setAllMatched([]);
    setAllInSheetNotManifest([]);
    setAllInManifestNotSheet([]);
    setDispatchInfo(null);

    try {
      // 1. Парсим манифест
      const uploadResponse = await uploadManifest(file);
      setManifestPilgrims(uploadResponse.pilgrims);

      // 2. Если тур выбран — сравниваем по пакетам
      if (selectedTour) {
        await compareByPackages(uploadResponse.pilgrims);
      }
    } catch (error) {
      console.error("Error uploading manifest:", error);
      setManifestError("Ошибка загрузки манифеста. Проверьте формат файла.");
    } finally {
      setIsUploadingManifest(false);
    }
  };

  const compareByPackages = async (mPilgrims: Pilgrim[]) => {
    if (!selectedTour) return;

    setIsComparing(true);
    setManifestError(null);

    try {
      const normalizedManifestPilgrims = dedupeManifestPilgrims(mPilgrims);

      const sheetResponse = await getSheetPilgrims(
        selectedTour.spreadsheet_id,
        selectedTour.sheet_name
      );

      const manifestKeyIndexMap = new Map<string, number[]>();
      normalizedManifestPilgrims.forEach((p, index) => {
        const keys = buildMatchKeys(p);
        for (const key of keys) {
          const indexes = manifestKeyIndexMap.get(key) || [];
          indexes.push(index);
          manifestKeyIndexMap.set(key, indexes);
        }
      });

      const matchedManifestIndexes = new Set<number>();
      const matched: MatchedPilgrim[] = [];
      const inSheetNotManifest: PilgrimWithPackage[] = [];
      const matchedByPassport: MatchedPilgrim[] = [];
      const matchedByFuzzyName: MatchedPilgrim[] = [];

      for (const pkg of sheetResponse.packages) {
        for (const p of pkg.pilgrims) {
          const withPkg: PilgrimWithPackage = {
            ...p,
            package_name: pkg.package_name,
            tour_name: selectedTour.sheet_name,
          };

          const sheetKeys = buildMatchKeys(withPkg);
          let matchedManifestIndex: number | null = null;

          for (const key of sheetKeys) {
            const manifestIndexes = manifestKeyIndexMap.get(key);
            if (!manifestIndexes || manifestIndexes.length === 0) continue;

            while (manifestIndexes.length > 0) {
              const manifestIndex = manifestIndexes.shift();
              if (manifestIndex === undefined) break;
              if (!matchedManifestIndexes.has(manifestIndex)) {
                matchedManifestIndexes.add(manifestIndex);
                matchedManifestIndex = manifestIndex;
                break;
              }
            }

            if (matchedManifestIndex !== null) break;
          }

          if (matchedManifestIndex !== null) {
            const manifestPilgrim = normalizedManifestPilgrims[matchedManifestIndex];
            matched.push({
              ...manifestPilgrim,
              // В совпадениях ФИО/документ берём из манифеста, пакет — из таблицы
              package_name: withPkg.package_name,
              tour_name: withPkg.tour_name,
              iin: manifestPilgrim.iin || withPkg.iin,
            });
          } else {
            inSheetNotManifest.push(withPkg);
          }
        }
      }

      // Второй проход: в первую очередь пробуем "похожий паспорт + близкое ФИО".
      const passportUnmatchedSheet: PilgrimWithPackage[] = [];
      for (const sheetPilgrim of inSheetNotManifest) {
        const passportDrivenIndex = findPassportDrivenManifestMatchIndex(
          sheetPilgrim,
          normalizedManifestPilgrims,
          matchedManifestIndexes
        );

        if (passportDrivenIndex === null) {
          passportUnmatchedSheet.push(sheetPilgrim);
          continue;
        }

        matchedManifestIndexes.add(passportDrivenIndex);
        const manifestPilgrim = normalizedManifestPilgrims[passportDrivenIndex];
        const matchedPilgrim: MatchedPilgrim = {
          ...manifestPilgrim,
          package_name: sheetPilgrim.package_name,
          tour_name: sheetPilgrim.tour_name,
          iin: manifestPilgrim.iin || sheetPilgrim.iin,
        };
        matched.push(matchedPilgrim);
        matchedByPassport.push(matchedPilgrim);
      }

      // Третий проход: нестрогое совпадение по ФИО + похожесть паспорта (если оба паспорта есть).
      const stillUnmatchedSheet: PilgrimWithPackage[] = [];
      for (const sheetPilgrim of passportUnmatchedSheet) {
        const fuzzyIndex = findFuzzyManifestMatchIndex(
          sheetPilgrim,
          normalizedManifestPilgrims,
          matchedManifestIndexes
        );

        if (fuzzyIndex === null) {
          stillUnmatchedSheet.push(sheetPilgrim);
          continue;
        }

        matchedManifestIndexes.add(fuzzyIndex);
        const manifestPilgrim = normalizedManifestPilgrims[fuzzyIndex];
        const matchedPilgrim: MatchedPilgrim = {
          ...manifestPilgrim,
          package_name: sheetPilgrim.package_name,
          tour_name: sheetPilgrim.tour_name,
          iin: manifestPilgrim.iin || sheetPilgrim.iin,
        };
        matched.push(matchedPilgrim);
        matchedByFuzzyName.push(matchedPilgrim);
      }

      if (matchedByPassport.length > 0 || matchedByFuzzyName.length > 0) {
        console.info(
          "Нестрогие совпадения",
          {
            byPassport: matchedByPassport.map((p) => `${p.surname} ${p.name} | ${p.document || "-"}`),
            byName: matchedByFuzzyName.map((p) => `${p.surname} ${p.name} | ${p.document || "-"}`),
          }
        );
      }

      const inManifestNotSheet: ManifestPilgrimWithPackage[] = [];
      normalizedManifestPilgrims.forEach((p, index) => {
        if (!matchedManifestIndexes.has(index)) {
          inManifestNotSheet.push({
            ...p,
            tour_name: selectedTour.sheet_name,
          });
        }
      });

      setAllMatched(matched);
      setAllInSheetNotManifest(stillUnmatchedSheet);
      setAllInManifestNotSheet(inManifestNotSheet);
    } catch (error) {
      console.error("Error comparing:", error);
      setManifestError("Ошибка сравнения с таблицей");
    } finally {
      setIsComparing(false);
    }
  };

  const hasResults = allMatched.length > 0 || allInSheetNotManifest.length > 0 || allInManifestNotSheet.length > 0;

  const handleAddToMatchedFromSheet = (index: number) => {
    const row = allInSheetNotManifest[index];
    if (!row) return;
    if (!normalizeDocument(row.document)) return;

    const addedRow: MatchedPilgrim = {
      surname: row.surname,
      name: row.name,
      document: row.document || "",
      iin: row.iin || "",
      manager: row.manager || "",
      package_name: row.package_name,
      tour_name: row.tour_name,
      tour_code: "",
      _sourceTable: "sheet",
    };

    setAllMatched((prev) => {
      const alreadyExists = prev.some((p) =>
        normalizeNamePart(p.surname) === normalizeNamePart(addedRow.surname) &&
        normalizeNamePart(p.name) === normalizeNamePart(addedRow.name) &&
        normalizeDocument(p.document) === normalizeDocument(addedRow.document) &&
        (p.package_name || "") === (addedRow.package_name || "")
      );
      if (alreadyExists) return prev;
      return [...prev, addedRow];
    });

    setAllInSheetNotManifest((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddToMatchedFromManifest = (index: number) => {
    const row = allInManifestNotSheet[index];
    if (!row) return;
    if (!normalizeDocument(row.document)) return;

    const addedRow: MatchedPilgrim = {
      surname: row.surname,
      name: row.name,
      document: row.document || "",
      iin: row.iin || "",
      manager: "",
      package_name: row.package_name || "",
      tour_name: row.tour_name || (selectedTour?.sheet_name || ""),
      tour_code: "",
      _sourceTable: "manifest",
    };

    setAllMatched((prev) => {
      const alreadyExists = prev.some((p) =>
        normalizeNamePart(p.surname) === normalizeNamePart(addedRow.surname) &&
        normalizeNamePart(p.name) === normalizeNamePart(addedRow.name) &&
        normalizeDocument(p.document) === normalizeDocument(addedRow.document) &&
        (p.package_name || "") === (addedRow.package_name || "")
      );
      if (alreadyExists) return prev;
      return [...prev, addedRow];
    });

    setAllInManifestNotSheet((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreateTourCode = async () => {
    if (!selectedTour) {
      setManifestError("Сначала выберите тур");
      return;
    }
    if (!selectedHotel || !selectedFlight || !selectedCountry) {
      setManifestError("Заполните страну, рейс и отель");
      return;
    }
    if (!hasResults && (!manifestFile || manifestPilgrims.length === 0)) {
      setManifestError("Сначала загрузите манифест");
      return;
    }
    if (allMatched.length === 0) {
      setManifestError("Нет совпадений для отправки");
      return;
    }

    setIsQueueingDispatch(true);
    setManifestError(null);
    setDispatchInfo(null);

    try {
      const response = await enqueueDispatchJob({
        tour: {
          spreadsheet_id: selectedTour.spreadsheet_id,
          spreadsheet_name: selectedTour.spreadsheet_name,
          sheet_name: selectedTour.sheet_name,
          date_start: selectedTour.date_start,
          date_end: selectedTour.date_end,
          days: selectedTour.days,
          route: selectedTour.route,
          departure_city: selectedTour.departure_city,
        },
        selection: {
          country: selectedCountry,
          hotel: selectedHotel,
          flight: selectedFlight,
          remark: "",
        },
        dispatch_overrides: {
          q_touragent: dispatchTouragentName.trim(),
          q_touragent_bin: dispatchTouragentBin.trim(),
        },
        results: {
          matched: allMatched.map((p) => ({
            surname: p.surname,
            name: p.name,
            document: p.document || "",
            package_name: p.package_name,
            tour_name: p.tour_name,
          })),
          in_sheet_not_in_manifest: allInSheetNotManifest.map((p) => ({
            surname: p.surname,
            name: p.name,
            document: p.document || "",
            package_name: p.package_name,
            tour_name: p.tour_name,
          })),
          in_manifest_not_in_sheet: allInManifestNotSheet.map((p) => ({
            surname: p.surname,
            name: p.name,
            document: p.document || "",
            package_name: p.package_name || "",
            tour_name: p.tour_name || "",
          })),
        },
        manifest_filename: manifestFile.name,
      });

      setDispatchInfo(`Задача поставлена в очередь: ${response.id} (status: ${response.status})`);
    } catch (error) {
      console.error("Error queueing dispatch:", error);
      setManifestError("Не удалось поставить задачу в очередь");
    } finally {
      setIsQueueingDispatch(false);
    }
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

    const displayValue = value || "-";
    return (
      <button
        type="button"
        className={`${textClassName} text-left w-full`}
        onDoubleClick={() => beginEditCell(table, rowIndex, field, value)}
        title="Двойной клик для редактирования"
      >
        {displayValue}
      </button>
    );
  };

  const hotelOptions = selectedHotel && !hotels.includes(selectedHotel)
    ? [selectedHotel, ...hotels]
    : hotels;

  return (
    <div className="p-6 md:p-12">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl mb-2 text-[#2B2318]">Создать тур код</h1>
          <p className="text-[#6B5435]">
            Заполните данные для создания нового тур кода
          </p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl p-6 md:p-8 shadow-lg border border-[#E5DDD0]">
          <div className="space-y-6">
            {isPrefillingFromPackage && (
              <p className="text-sm text-[#6B5435]">
                Загружаю сохраненные данные выбранного тура...
              </p>
            )}
            {/* Поиск туров по дате */}
            <div className="space-y-4">
              <div>
                <label className="block mb-2 text-[#2B2318] flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-[#B8985F]" />
                  Поиск туров по дате вылета
                </label>
                <div className="flex gap-2">
                  <Input
                    type="text"
                    value={dateInput}
                    onChange={(e) => setDateInput(e.target.value)}
                    placeholder="Введите дату (например, 17.02)"
                    className="bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleSearchTours();
                      }
                    }}
                  />
                  <Button
                    onClick={handleSearchTours}
                    disabled={isLoadingTours}
                    className="bg-gradient-to-r from-[#B8985F] to-[#A88952] hover:from-[#A88952] hover:to-[#8B6F47] text-white"
                  >
                    {isLoadingTours ? "Поиск..." : "Найти"}
                  </Button>
                </div>
                {tourSearchError && (
                  <p className="mt-2 text-sm text-red-600">{tourSearchError}</p>
                )}
              </div>

              {/* Результаты поиска туров */}
              {tourOptions.length > 0 && (
                <div>
                  <h4 className="mb-3 text-[#2B2318]">
                    Найдено туров: {tourOptions.length}
                  </h4>
                  <div className="space-y-2">
                    {tourOptions.map((tour, index) => {
                      const isSelected = selectedTour?.spreadsheet_id === tour.spreadsheet_id
                        && selectedTour?.sheet_name === tour.sheet_name;
                      return (
                        <div
                          key={index}
                          onClick={() => handleTourSelect(tour)}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                            isSelected
                              ? "bg-gradient-to-r from-[#B8985F]/40 to-[#A88952]/30 border-[#B8985F] shadow-lg ring-2 ring-[#B8985F]/50"
                              : "bg-[#F5F1EA] border-[#E5DDD0] hover:border-[#B8985F] hover:shadow-md"
                          }`}
                        >
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                            <div>
                              <p className="text-xs text-[#6B5435]">Период тура</p>
                              <p className="text-sm text-[#2B2318] font-medium">
                                {tour.date_start} - {tour.date_end}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-[#6B5435]">Продолжительность</p>
                              <p className="text-sm text-[#2B2318] font-medium">
                                {tour.days} {tour.days === 1 ? "день" : tour.days < 5 ? "дня" : "дней"}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-[#6B5435]">Маршрут</p>
                              <p className="text-sm text-[#2B2318] font-medium">{tour.route}</p>
                            </div>
                            <div>
                              <p className="text-xs text-[#6B5435]">Город вылета</p>
                              <p className="text-sm text-[#2B2318] font-medium">{tour.departure_city}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Диапазон дат и количество дней */}
            {dateRange && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gradient-to-r from-[#F5F1EA] to-[#F5F1EA]/50 p-4 rounded-lg border border-[#E5DDD0]">
                  <label className="block mb-1 text-sm text-[#2B2318] flex items-center gap-2">
                    <Calendar className="w-3 h-3 text-[#B8985F]" />
                    Период тура
                  </label>
                  <div className="text-base text-[#2B2318]">{dateRange}</div>
                </div>
                <div className="bg-gradient-to-r from-[#F5F1EA] to-[#F5F1EA]/50 p-4 rounded-lg border border-[#E5DDD0]">
                  <label className="block mb-1 text-sm text-[#2B2318] flex items-center gap-2">
                    <Clock className="w-3 h-3 text-[#B8985F]" />
                    Продолжительность
                  </label>
                  <div className="text-base text-[#2B2318]">
                    {days} {days === 1 ? "день" : days < 5 ? "дня" : "дней"}
                  </div>
                </div>
              </div>
            )}

            {/* Страна и отель */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block mb-2 text-[#2B2318] flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#B8985F]" />
                  Страна
                </label>
                <Select value={selectedCountry} onValueChange={setSelectedCountry}>
                  <SelectTrigger className="bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Саудовская Аравия">Саудовская Аравия</SelectItem>
                    <SelectItem value="ОАЭ">ОАЭ</SelectItem>
                    <SelectItem value="Турция">Турция</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block mb-2 text-[#2B2318] flex items-center gap-2">
                  <Building className="w-4 h-4 text-[#B8985F]" />
                  Название отеля
                </label>
                <Select value={selectedHotel} onValueChange={setSelectedHotel}>
                  <SelectTrigger className="bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]">
                    <SelectValue placeholder="Выберите отель" />
                  </SelectTrigger>
                  <SelectContent>
                    {hotelOptions.map((hotel) => (
                      <SelectItem key={hotel} value={hotel}>
                        {hotel}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="border border-[#E5DDD0] rounded-lg p-4 bg-[#F5F1EA]/40">
              <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-[#E5DDD0] hover:bg-white"
                    onClick={applyHickmetPreset}
                  >
                    HICKMET PREMIUM
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-[#E5DDD0] hover:bg-white"
                    onClick={applyNiyetPreset}
                  >
                    NIYET
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-[#E5DDD0] hover:bg-white"
                    onClick={clearDispatchOverrides}
                  >
                    Очистить
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block mb-1 text-sm text-[#2B2318]">Турагент</label>
                  <Input
                    value={dispatchTouragentName}
                    onChange={(e) => setDispatchTouragentName(e.target.value)}
                    className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                  />
                </div>
                <div>
                  <label className="block mb-1 text-sm text-[#2B2318]">БИН турагента</label>
                  <Input
                    value={dispatchTouragentBin}
                    onChange={(e) => setDispatchTouragentBin(e.target.value)}
                    className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                  />
                </div>
              </div>
            </div>

            {/* Манифест */}
            <div className="border-t border-[#E5DDD0] pt-6">
              <h3 className="mb-4 text-[#2B2318] flex items-center gap-2">
                <Upload className="w-5 h-5 text-[#B8985F]" />
                Парсинг манифеста
              </h3>

              <div className="mb-4">
                <label className="block mb-2 text-sm text-[#2B2318]">
                  Данные манифеста
                </label>
                <div
                  className="mt-3 border-2 border-dashed border-[#E5DDD0] rounded-lg p-6 text-center cursor-pointer hover:border-[#B8985F] hover:bg-[#F5F1EA]/50 transition-all"
                  onClick={() => document.getElementById('manifest-file-input')?.click()}
                >
                  <input
                    id="manifest-file-input"
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={handleManifestUpload}
                    className="hidden"
                  />
                  <Upload className="w-8 h-8 mx-auto mb-2 text-[#B8985F]" />
                  {manifestFile ? (
                    <p className="text-sm text-[#2B2318]">{manifestFile.name}</p>
                  ) : (
                    <>
                      <p className="text-sm text-[#2B2318] font-medium">Нажмите для загрузки файла</p>
                      <p className="text-xs text-[#6B5435] mt-1">Поддерживаются форматы: .xlsx, .xls, .csv</p>
                    </>
                  )}
                  {(isUploadingManifest || isComparing) && (
                    <p className="text-sm text-[#B8985F] mt-2">
                      {isComparing ? "Сравнение с таблицей..." : "Загрузка..."}
                    </p>
                  )}
                </div>
                {manifestError && (
                  <p className="mt-2 text-sm text-red-600">{manifestError}</p>
                )}
              </div>

              {/* Статистика */}
              {hasResults && (
                <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-green-50 p-3 rounded-lg border border-green-200 text-center">
                    <p className="text-2xl font-bold text-green-700">{allMatched.length}</p>
                    <p className="text-xs text-green-600">Совпадений</p>
                  </div>
                  <div className="bg-orange-50 p-3 rounded-lg border border-orange-200 text-center">
                    <p className="text-2xl font-bold text-orange-700">{allInSheetNotManifest.length}</p>
                    <p className="text-xs text-orange-600">В таблице, нет в манифесте</p>
                  </div>
                  <div className="bg-red-50 p-3 rounded-lg border border-red-200 text-center">
                    <p className="text-2xl font-bold text-red-700">{allInManifestNotSheet.length}</p>
                    <p className="text-xs text-red-600">В манифесте, нет в таблице</p>
                  </div>
                </div>
              )}

              {/* Таблица 1: Совпадения */}
              {allMatched.length > 0 && (
                <div className="mb-6">
                  <h4 className="mb-2 text-[#2B2318] font-medium">
                    Совпадения ({allMatched.length})
                  </h4>
                  <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-green-50 hover:bg-green-50">
                          <TableHead className="text-[#2B2318] w-12">№</TableHead>
                          <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                          <TableHead className="text-[#2B2318]">Имя</TableHead>
                          <TableHead className="text-[#2B2318]">Паспорт</TableHead>
                          <TableHead className="text-[#2B2318]">Пакет</TableHead>
                          <TableHead className="text-[#2B2318]">Тур</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {allMatched.map((p, i) => (
                          <TableRow
                            key={`m-${p.document}-${i}`}
                            className="hover:bg-green-50/30 cursor-pointer"
                            onDoubleClick={() => openMatchedEditor(i)}
                            title="Двойной клик для редактирования"
                          >
                            <TableCell className="text-[#6B5435]">{i + 1}</TableCell>
                            <TableCell className="text-[#2B2318]">{p.surname}</TableCell>
                            <TableCell className="text-[#2B2318]">{p.name}</TableCell>
                            <TableCell className="text-[#6B5435]">{p.document || "-"}</TableCell>
                            <TableCell className="text-[#6B5435]">{p.package_name}</TableCell>
                            <TableCell className="text-[#6B5435]">{p.tour_name}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Таблица 2: В таблице, нет в манифесте */}
              {allInSheetNotManifest.length > 0 && (
                <div className="mb-6">
                  <h4 className="mb-2 text-[#2B2318] font-medium">
                    В таблице, нет в манифесте ({allInSheetNotManifest.length})
                  </h4>
                  <div className="border border-[#FFD4A3] rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-[#FFF4E6] hover:bg-[#FFF4E6]">
                          <TableHead className="text-[#2B2318] w-12">№</TableHead>
                          <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                          <TableHead className="text-[#2B2318]">Имя</TableHead>
                          <TableHead className="text-[#2B2318]">Паспорт</TableHead>
                          <TableHead className="text-[#2B2318]">Пакет</TableHead>
                          <TableHead className="text-[#2B2318]">Добавить</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {allInSheetNotManifest.map((p, i) => (
                          <TableRow key={`s-${p.surname}-${p.name}-${p.document}-${i}`} className="hover:bg-[#FFF4E6]/30">
                            <TableCell className="text-[#6B5435]">{i + 1}</TableCell>
                            <TableCell>
                              {renderEditableCell("sheet", i, "surname", p.surname, "text-[#2B2318]")}
                            </TableCell>
                            <TableCell>
                              {renderEditableCell("sheet", i, "name", p.name, "text-[#2B2318]")}
                            </TableCell>
                            <TableCell>
                              {renderEditableCell("sheet", i, "document", p.document || "", "text-[#6B5435]")}
                            </TableCell>
                            <TableCell className="text-[#6B5435]">{p.package_name}</TableCell>
                            <TableCell>
                              {normalizeDocument(p.document) ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                                  onClick={() => handleAddToMatchedFromSheet(i)}
                                >
                                  Добавить
                                </Button>
                              ) : (
                                <span className="text-[#6B5435]">-</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Таблица 3: В манифесте, нет в таблице */}
              {allInManifestNotSheet.length > 0 && (
                <div className="mb-6">
                  <h4 className="mb-2 text-[#2B2318] font-medium">
                    В манифесте, нет в таблице ({allInManifestNotSheet.length})
                  </h4>
                  <div className="border border-red-200 rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-red-50 hover:bg-red-50">
                          <TableHead className="text-[#2B2318] w-12">№</TableHead>
                          <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                          <TableHead className="text-[#2B2318]">Имя</TableHead>
                          <TableHead className="text-[#2B2318]">Паспорт</TableHead>
                          <TableHead className="text-[#2B2318]">Пакет</TableHead>
                          <TableHead className="text-[#2B2318]">Тур</TableHead>
                          <TableHead className="text-[#2B2318]">Добавить</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {allInManifestNotSheet.map((p, i) => (
                          <TableRow key={`n-${p.document}-${i}`} className="hover:bg-red-50/30">
                            <TableCell className="text-[#6B5435]">{i + 1}</TableCell>
                            <TableCell>
                              {renderEditableCell("manifest", i, "surname", p.surname, "text-[#2B2318]")}
                            </TableCell>
                            <TableCell>
                              {renderEditableCell("manifest", i, "name", p.name, "text-[#2B2318]")}
                            </TableCell>
                            <TableCell>
                              {renderEditableCell("manifest", i, "document", p.document || "", "text-[#6B5435]")}
                            </TableCell>
                            <TableCell className="text-[#6B5435]">{p.package_name || "-"}</TableCell>
                            <TableCell className="text-[#6B5435]">{p.tour_name || "-"}</TableCell>
                            <TableCell>
                              {normalizeDocument(p.document) ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                                  onClick={() => handleAddToMatchedFromManifest(i)}
                                >
                                  Добавить
                                </Button>
                              ) : (
                                <span className="text-[#6B5435]">-</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </div>

            {/* Кнопки */}
            <div className="flex gap-4 pt-4 border-t border-[#E5DDD0]">
              <Button
                onClick={handleCreateTourCode}
                disabled={!selectedDateShort || !selectedFlight || !selectedHotel || isQueueingDispatch}
                className="bg-gradient-to-r from-[#B8985F] to-[#A88952] hover:from-[#A88952] hover:to-[#8B6F47] text-white"
              >
                <Plus className="w-4 h-4 mr-2" />
                {isQueueingDispatch ? "Постановка в очередь..." : "Создать тур код"}
              </Button>
              <Button
                variant="outline"
                className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
              >
                Отмена
              </Button>
            </div>
            {dispatchInfo && (
              <p className="text-sm text-green-700">{dispatchInfo}</p>
            )}

            {matchedEditor && (
              <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
                <div className="w-full max-w-lg rounded-xl border border-[#E5DDD0] bg-white p-5 shadow-2xl">
                  <h4 className="text-[#2B2318] font-medium mb-4">Редактирование совпадения</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block mb-1 text-sm text-[#2B2318]">Фамилия</label>
                      <Input
                        value={matchedEditor.draft.surname || ""}
                        onChange={(e) => updateMatchedEditorField("surname", e.target.value)}
                        className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                      />
                    </div>
                    <div>
                      <label className="block mb-1 text-sm text-[#2B2318]">Имя</label>
                      <Input
                        value={matchedEditor.draft.name || ""}
                        onChange={(e) => updateMatchedEditorField("name", e.target.value)}
                        className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                      />
                    </div>
                    <div>
                      <label className="block mb-1 text-sm text-[#2B2318]">Паспорт</label>
                      <Input
                        value={matchedEditor.draft.document || ""}
                        onChange={(e) => updateMatchedEditorField("document", e.target.value)}
                        className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                      />
                    </div>
                    <div>
                      <label className="block mb-1 text-sm text-[#2B2318]">Пакет</label>
                      <Input
                        value={matchedEditor.draft.package_name || ""}
                        onChange={(e) => updateMatchedEditorField("package_name", e.target.value)}
                        className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block mb-1 text-sm text-[#2B2318]">Тур</label>
                      <Input
                        value={matchedEditor.draft.tour_name || ""}
                        onChange={(e) => updateMatchedEditorField("tour_name", e.target.value)}
                        className="bg-white border-[#E5DDD0] focus:border-[#B8985F]"
                      />
                    </div>
                  </div>

                  <div className="mt-5 space-y-2">
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button
                        type="button"
                        className="w-full sm:w-[210px] bg-gradient-to-r from-[#B96464] to-[#A95555] hover:from-[#A95555] hover:to-[#944848] text-white shadow-sm"
                        onClick={deleteMatchedEditorRow}
                      >
                        Удалить запись
                      </Button>
                      <Button
                        type="button"
                        className="w-full sm:w-[210px] bg-gradient-to-r from-[#5E8C6B] to-[#4F7B5C] hover:from-[#4F7B5C] hover:to-[#446A50] text-white shadow-sm"
                        onClick={saveMatchedEditor}
                      >
                        Сохранить
                      </Button>
                    </div>
                    <div className="flex flex-wrap justify-center gap-2">
                      {matchedEditor.draft._sourceTable && (
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full sm:w-[300px] border-[#D8CCB8] bg-[#FCF8F2] text-[#6B5435] hover:bg-[#F2E9DB]"
                          onClick={returnMatchedToSource}
                        >
                          Вернуть в предыдущую таблицу
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full sm:w-[210px] border-[#D8CCB8] bg-white text-[#6B5435] hover:bg-[#F5F1EA]"
                        onClick={() => setMatchedEditor(null)}
                      >
                        Отмена
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
