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
  getTourPackage,
  listTourPackages,
  TourPackageDetailResponse,
  TourPackageSummary,
} from "../../src/lib/api/tourPackages";
import { useNavigate } from "react-router";

const toIsoDate = (dateValue: string): string => {
  const parts = dateValue.split(".");
  if (parts.length !== 3) return "";
  const [dd, mm, yyyy] = parts;
  if (!dd || !mm || !yyyy) return "";
  return `${yyyy}-${mm}-${dd}`;
};

export function TourPackages() {
  const navigate = useNavigate();
  const [tourPackages, setTourPackages] = useState<TourPackageSummary[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [selectedPackageDetail, setSelectedPackageDetail] = useState<TourPackageDetailResponse | null>(null);
  const [searchDate, setSearchDate] = useState("");
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTourPackages = async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      const response = await listTourPackages();
      setTourPackages(response.items);
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
    } catch (e) {
      console.error("Error loading tour package detail:", e);
      setSelectedPackageDetail(null);
      setError("Не удалось загрузить данные тура");
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    loadTourPackages();
  }, []);

  const filteredPackages = useMemo(() => {
    if (!searchDate) return tourPackages;
    return tourPackages.filter((pkg) => {
      const startIso = toIsoDate(pkg.date_start);
      const endIso = toIsoDate(pkg.date_end);
      return startIso.includes(searchDate) || endIso.includes(searchDate);
    });
  }, [searchDate, tourPackages]);

  const handleSelectPackage = async (tourId: string) => {
    setSelectedPackageId(tourId);
    setSelectedPackageDetail(null);
    await loadTourPackageDetail(tourId);
  };

  const matchedCount = selectedPackageDetail?.matched.length || 0;
  const inSheetOnlyCount = selectedPackageDetail?.in_sheet_not_in_manifest.length || 0;
  const inManifestOnlyCount = selectedPackageDetail?.in_manifest_not_in_sheet.length || 0;

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
                    onClick={() => navigate(`/create?tourId=${selectedPackageDetail.id}`)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Создать
                  </Button>
                )}
              </div>

              {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

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
                            {selectedPackageDetail.matched.map((row, idx) => (
                              <TableRow key={row.id}>
                                <TableCell>{idx + 1}</TableCell>
                                <TableCell>{row.surname}</TableCell>
                                <TableCell>{row.name}</TableCell>
                                <TableCell>{row.document || "-"}</TableCell>
                                <TableCell>{row.package_name || "-"}</TableCell>
                                <TableCell>{row.tour_code || "-"}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>

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
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {selectedPackageDetail.in_sheet_not_in_manifest.map((row, idx) => (
                              <TableRow key={`${row.surname}-${row.name}-${row.document}-${idx}`}>
                                <TableCell>{idx + 1}</TableCell>
                                <TableCell>{row.surname}</TableCell>
                                <TableCell>{row.name}</TableCell>
                                <TableCell>{row.document || "-"}</TableCell>
                                <TableCell>{row.package_name || "-"}</TableCell>
                                <TableCell>-</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>

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
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {selectedPackageDetail.in_manifest_not_in_sheet.map((row, idx) => (
                              <TableRow key={`${row.surname}-${row.name}-${row.document}-${idx}`}>
                                <TableCell>{idx + 1}</TableCell>
                                <TableCell>{row.surname}</TableCell>
                                <TableCell>{row.name}</TableCell>
                                <TableCell>{row.document || "-"}</TableCell>
                                <TableCell>{row.package_name || "-"}</TableCell>
                                <TableCell>-</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
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
    </div>
  );
}
