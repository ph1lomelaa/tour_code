import { useState } from "react";
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
import { Textarea } from "../components/ui/textarea";
import { searchToursByDate, TourOption } from "../../src/lib/api/tours";
import { uploadManifest, compareManifestWithSheet, Pilgrim } from "../../src/lib/api/manifest";

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

type DisplayPilgrim = {
  id: number;
  lastName: string;
  firstName: string;
  passportNumber: string;
  manager: string;
};

export function CreateTourCode() {
  const [selectedDateShort, setSelectedDateShort] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [days, setDays] = useState(0);
  const [availableFlights, setAvailableFlights] = useState<string[]>([]);
  const [selectedFlight, setSelectedFlight] = useState("");
  const [selectedCountry, setSelectedCountry] = useState("Саудовская Аравия");
  const [selectedHotel, setSelectedHotel] = useState("");
  const [parsedPilgrims, setParsedPilgrims] = useState<DisplayPilgrim[]>([]);

  // Manifest state
  const [manifestFile, setManifestFile] = useState<File | null>(null);
  const [manifestPilgrims, setManifestPilgrims] = useState<Pilgrim[]>([]);
  const [isUploadingManifest, setIsUploadingManifest] = useState(false);
  const [manifestError, setManifestError] = useState<string | null>(null);

  // Comparison results
  const [matchedPilgrims, setMatchedPilgrims] = useState<Pilgrim[]>([]);
  const [inSheetNotInManifest, setInSheetNotInManifest] = useState<Pilgrim[]>([]);
  const [inManifestNotInSheet, setInManifestNotInSheet] = useState<Pilgrim[]>([]);
  const [isComparing, setIsComparing] = useState(false);

  const [tourOptions, setTourOptions] = useState<TourOption[]>([]);
  const [isLoadingTours, setIsLoadingTours] = useState(false);
  const [tourSearchError, setTourSearchError] = useState<string | null>(null);
  const [dateInput, setDateInput] = useState("");
  const [selectedTour, setSelectedTour] = useState<TourOption | null>(null);

  const mapPilgrimsToDisplay = (pilgrims: Pilgrim[]) =>
    pilgrims.map((p, index) => ({
      id: index + 1,
      lastName: p.surname,
      firstName: p.name,
      passportNumber: p.document,
      manager: p.manager ?? "",
    }));
  const calculateDays = (start: string, end: string) => {
    const [dayS, monthS, yearS] = start.split(".");
    const [dayE, monthE, yearE] = end.split(".");
    const startDate = new Date(
      parseInt(yearS),
      parseInt(monthS) - 1,
      parseInt(dayS)
    );
    const endDate = new Date(
      parseInt(yearE),
      parseInt(monthE) - 1,
      parseInt(dayE)
    );
    const diffTime = Math.abs(endDate.getTime() - startDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  // Обработка поиска туров по дате
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

  // Обработка выбора конкретного тура из результатов поиска
  const handleTourSelect = (tour: TourOption) => {
    setSelectedTour(tour);
    setSelectedDateShort(tour.date_start);
    const range = `${tour.date_start} - ${tour.date_end}`;
    setDateRange(range);
    setDays(tour.days);
    setAvailableFlights([tour.route]);
    setSelectedFlight(tour.route);
  };

  // Обработка загрузки Excel манифеста
  const handleManifestUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setManifestFile(file);
    setIsUploadingManifest(true);
    setManifestError(null);

    try {
      const response = await uploadManifest(file);
      setManifestPilgrims(response.pilgrims);
      setParsedPilgrims(mapPilgrimsToDisplay(response.pilgrims));

      // Автоматически сравниваем с выбранным листом
      if (selectedTour) {
        await compareWithSheet(response.pilgrims);
      }
    } catch (error) {
      console.error("Error uploading manifest:", error);
      setManifestError("Ошибка загрузки манифеста. Проверьте формат файла.");
    } finally {
      setIsUploadingManifest(false);
    }
  };

  // Сравнение манифеста с Google Sheets
  const compareWithSheet = async (pilgrims: Pilgrim[]) => {
    if (!selectedTour) {
      setManifestError("Сначала выберите тур");
      return;
    }

    setIsComparing(true);
    setManifestError(null);

    try {
      const response = await compareManifestWithSheet({
        spreadsheet_id: selectedTour.spreadsheet_id,
        sheet_name: selectedTour.sheet_name,
        manifest_pilgrims: pilgrims,
      });

      setMatchedPilgrims(response.matched);
      setInSheetNotInManifest(response.in_sheet_not_in_manifest);
      setInManifestNotInSheet(response.in_manifest_not_in_sheet);
    } catch (error) {
      console.error("Error comparing:", error);
      setManifestError("Ошибка сравнения с таблицей");
    } finally {
      setIsComparing(false);
    }
  };

  // Удаление паломника из списка совпадений
  const handleRemovePilgrim = (document: string) => {
    setMatchedPilgrims(prev => prev.filter(p => p.document !== document));
  };

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
                      const isSelected = selectedTour?.date_start === tour.date_start && selectedTour?.route === tour.route;
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
              {/* Страна */}
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

              {/* Отель */}
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
                    {hotels.map((hotel) => (
                      <SelectItem key={hotel} value={hotel}>
                        {hotel}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Разделитель */}
            <div className="border-t border-[#E5DDD0] pt-6">
              <h3 className="mb-4 text-[#2B2318] flex items-center gap-2">
                <Upload className="w-5 h-5 text-[#B8985F]" />
                Парсинг манифеста
              </h3>

              {/* Загрузка манифеста */}
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
                  {isUploadingManifest && (
                    <p className="text-sm text-[#B8985F] mt-2">Загрузка...</p>
                  )}
                </div>
                {manifestError && (
                  <p className="mt-2 text-sm text-red-600">{manifestError}</p>
                )}
              </div>

              {/* Таблица паломников из манифеста */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-[#2B2318]">
                    Список паломников ({parsedPilgrims.length})
                  </h4>
                </div>

                <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-[#F5F1EA] hover:bg-[#F5F1EA]">
                        <TableHead className="text-[#2B2318]">№</TableHead>
                        <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                        <TableHead className="text-[#2B2318]">Имя</TableHead>
                        <TableHead className="text-[#2B2318]">Номер паспорта</TableHead>
                        <TableHead className="text-[#2B2318]">Менеджер</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {parsedPilgrims.map((pilgrim, index) => (
                        <TableRow key={pilgrim.id} className="hover:bg-[#F5F1EA]/50">
                          <TableCell className="text-[#6B5435]">{index + 1}</TableCell>
                          <TableCell className="text-[#2B2318]">{pilgrim.lastName}</TableCell>
                          <TableCell className="text-[#2B2318]">{pilgrim.firstName}</TableCell>
                          <TableCell className="text-[#6B5435]">{pilgrim.passportNumber}</TableCell>
                          <TableCell className="text-[#6B5435]">{pilgrim.manager}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Паломники из таблицы, которых нет в манифесте */}
              {inSheetNotInManifest.length > 0 && (
                <div className="bg-gradient-to-r from-[#FFF4E6] to-[#FFE5CC]/50 p-4 rounded-lg border border-[#FFD4A3]">
                  <h4 className="mb-3 text-[#2B2318] flex items-center gap-2">
                    Есть в таблице, но отсутствуют в манифесте ({inSheetNotInManifest.length})
                  </h4>

                  <div className="border border-[#FFD4A3] rounded-lg overflow-hidden bg-white">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-[#FFF4E6] hover:bg-[#FFF4E6]">
                          <TableHead className="text-[#2B2318]">№</TableHead>
                          <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                          <TableHead className="text-[#2B2318]">Имя</TableHead>
                          <TableHead className="text-[#2B2318]">Номер паспорта</TableHead>
                          <TableHead className="text-[#2B2318]">Менеджер</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inSheetNotInManifest.map((pilgrim, index) => (
                        <TableRow key={`${pilgrim.document}-${index}`} className="hover:bg-[#FFF4E6]/30">
                          <TableCell className="text-[#6B5435]">{index + 1}</TableCell>
                          <TableCell className="text-[#2B2318]">{pilgrim.surname}</TableCell>
                          <TableCell className="text-[#2B2318]">{pilgrim.name}</TableCell>
                          <TableCell className="text-[#6B5435]">{pilgrim.document}</TableCell>
                          <TableCell className="text-[#6B5435]">{pilgrim.manager}</TableCell>
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
                disabled={!selectedDateShort || !selectedFlight || !selectedHotel}
                className="bg-gradient-to-r from-[#B8985F] to-[#A88952] hover:from-[#A88952] hover:to-[#8B6F47] text-white"
              >
                <Plus className="w-4 h-4 mr-2" />
                Создать тур код
              </Button>
              <Button
                variant="outline"
                className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
              >
                Отмена
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
