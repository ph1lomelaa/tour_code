import { useState } from "react";
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

// Mock data
const tourPackages = [
  { id: 1, date: "2026-03-15", name: "Авиа", pilgrimsCount: 45 },
  { id: 2, date: "2026-03-20", name: "Авиа Премиум", pilgrimsCount: 30 },
  { id: 3, date: "2026-04-01", name: "Автобус", pilgrimsCount: 52 },
  { id: 4, date: "2026-04-10", name: "Авиа", pilgrimsCount: 38 },
];

const mockPilgrims = [
  {
    id: 1,
    name: "Иванов Иван Иванович",
    passportNumber: "1234 567890",
    tourCode: "HKM-2026-001",
  },
  {
    id: 2,
    name: "Петров Петр Петрович",
    passportNumber: "2345 678901",
    tourCode: "HKM-2026-002",
  },
  {
    id: 3,
    name: "Сидорова Мария Александровна",
    passportNumber: "3456 789012",
    tourCode: "HKM-2026-003",
  },
];

export function TourPackages() {
  const [selectedPackage, setSelectedPackage] = useState<number | null>(null);
  const [searchDate, setSearchDate] = useState("");

  const filteredPackages = tourPackages.filter((pkg) =>
    pkg.date.includes(searchDate)
  );

  return (
    <div className="p-12">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl mb-2 text-[#2B2318]">Пакеты с тур кодом</h1>
          <p className="text-[#6B5435]">
            Просмотр и управление туристическими пакетами
          </p>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {/* Left Panel - Tour Packages List */}
          <div className="col-span-4">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
              <h2 className="mb-4 text-[#2B2318]">Список туров</h2>

              {/* Search by date */}
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

              {/* Tour packages list */}
              <div className="space-y-2">
                {filteredPackages.map((pkg) => (
                  <button
                    key={pkg.id}
                    onClick={() => setSelectedPackage(pkg.id)}
                    className={`
                      w-full text-left p-4 rounded-lg transition-all duration-200 border
                      ${
                        selectedPackage === pkg.id
                          ? "bg-gradient-to-r from-[#B8985F] to-[#A88952] text-white border-[#B8985F] shadow-md"
                          : "bg-[#F5F1EA] border-[#E5DDD0] hover:border-[#B8985F] text-[#2B2318]"
                      }
                    `}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <p className="text-sm opacity-90">{pkg.date}</p>
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          selectedPackage === pkg.id
                            ? "bg-white/20"
                            : "bg-[#B8985F]/10 text-[#8B6F47]"
                        }`}
                      >
                        {pkg.pilgrimsCount} чел.
                      </span>
                    </div>
                    <p className={selectedPackage === pkg.id ? "" : ""}>
                      {pkg.name}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right Panel - Pilgrims Table */}
          <div className="col-span-8">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-[#2B2318]">
                  {selectedPackage
                    ? `Паломники в туре ${
                        tourPackages.find((p) => p.id === selectedPackage)?.name
                      }`
                    : "Выберите тур"}
                </h2>
                {selectedPackage && (
                  <Button className="bg-gradient-to-r from-[#B8985F] to-[#A88952] hover:from-[#A88952] hover:to-[#8B6F47] text-white">
                    <Plus className="w-4 h-4 mr-2" />
                    Создать
                  </Button>
                )}
              </div>

              {selectedPackage ? (
                <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-[#F5F1EA] hover:bg-[#F5F1EA]">
                        <TableHead className="text-[#2B2318]">№</TableHead>
                        <TableHead className="text-[#2B2318]">ФИО</TableHead>
                        <TableHead className="text-[#2B2318]">
                          Номер паспорта
                        </TableHead>
                        <TableHead className="text-[#2B2318]">
                          Номер тур кода
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {mockPilgrims.map((pilgrim, index) => (
                        <TableRow
                          key={pilgrim.id}
                          className="hover:bg-[#F5F1EA]/50"
                        >
                          <TableCell className="text-[#6B5435]">
                            {index + 1}
                          </TableCell>
                          <TableCell className="text-[#2B2318]">
                            {pilgrim.name}
                          </TableCell>
                          <TableCell className="text-[#6B5435]">
                            {pilgrim.passportNumber}
                          </TableCell>
                          <TableCell>
                            <span className="inline-flex px-3 py-1 rounded-full bg-gradient-to-r from-[#B8985F]/10 to-[#A88952]/10 text-[#8B6F47] text-sm">
                              {pilgrim.tourCode}
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
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
