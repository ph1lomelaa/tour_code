import { useState } from "react";
import { Input } from "../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Search } from "lucide-react";

// Mock data для паломников
const allPilgrims = [
  {
    id: 1,
    lastName: "Иванов",
    firstName: "Иван",
    middleName: "Иванович",
    passportNumber: "1234 567890",
    tourCode: "HKM-2026-001",
    tourName: "Авиа",
    tourDate: "2026-03-15",
  },
  {
    id: 2,
    lastName: "Петров",
    firstName: "Петр",
    middleName: "Петрович",
    passportNumber: "2345 678901",
    tourCode: "HKM-2026-002",
    tourName: "Авиа Премиум",
    tourDate: "2026-03-20",
  },
  {
    id: 3,
    lastName: "Сидорова",
    firstName: "Мария",
    middleName: "Александровна",
    passportNumber: "3456 789012",
    tourCode: "HKM-2026-003",
    tourName: "Автобус",
    tourDate: "2026-04-01",
  },
  {
    id: 4,
    lastName: "Смирнов",
    firstName: "Алексей",
    middleName: "Викторович",
    passportNumber: "4567 890123",
    tourCode: "HKM-2026-004",
    tourName: "Авиа",
    tourDate: "2026-04-10",
  },
  {
    id: 5,
    lastName: "Кузнецова",
    firstName: "Елена",
    middleName: "Сергеевна",
    passportNumber: "5678 901234",
    tourCode: "HKM-2026-005",
    tourName: "Авиа Премиум",
    tourDate: "2026-03-20",
  },
  {
    id: 6,
    lastName: "Попов",
    firstName: "Дмитрий",
    middleName: "Андреевич",
    passportNumber: "6789 012345",
    tourCode: "HKM-2026-006",
    tourName: "Автобус",
    tourDate: "2026-04-01",
  },
];

export function Pilgrims() {
  const [searchLastName, setSearchLastName] = useState("");
  const [searchFirstName, setSearchFirstName] = useState("");

  // Фильтрация паломников по фамилии и имени
  const filteredPilgrims = allPilgrims.filter((pilgrim) => {
    const lastNameMatch = pilgrim.lastName
      .toLowerCase()
      .includes(searchLastName.toLowerCase());
    const firstNameMatch = pilgrim.firstName
      .toLowerCase()
      .includes(searchFirstName.toLowerCase());
    
    return lastNameMatch && firstNameMatch;
  });

  return (
    <div className="p-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl mb-2 text-[#2B2318]">Паломники</h1>
          <p className="text-[#6B5435]">
            Поиск паломников по фамилии и имени
          </p>
        </div>

        {/* Search Filters */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0] mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Поиск по фамилии */}
            <div>
              <label className="block text-sm mb-2 text-[#2B2318]">
                Фамилия
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8B6F47]" />
                <Input
                  type="text"
                  value={searchLastName}
                  onChange={(e) => setSearchLastName(e.target.value)}
                  placeholder="Введите фамилию"
                  className="pl-10 bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
            </div>

            {/* Поиск по имени */}
            <div>
              <label className="block text-sm mb-2 text-[#2B2318]">
                Имя
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8B6F47]" />
                <Input
                  type="text"
                  value={searchFirstName}
                  onChange={(e) => setSearchFirstName(e.target.value)}
                  placeholder="Введите имя"
                  className="pl-10 bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
            </div>
          </div>

          {/* Results count */}
          <div className="mt-4 text-sm text-[#6B5435]">
            Найдено паломников: {filteredPilgrims.length}
          </div>
        </div>

        {/* Pilgrims Table */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
          <h2 className="mb-6 text-[#2B2318]">Список паломников</h2>

          {filteredPilgrims.length > 0 ? (
            <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#F5F1EA] hover:bg-[#F5F1EA]">
                    <TableHead className="text-[#2B2318]">№</TableHead>
                    <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                    <TableHead className="text-[#2B2318]">Имя</TableHead>
                    <TableHead className="text-[#2B2318]">Отчество</TableHead>
                    <TableHead className="text-[#2B2318]">
                      Номер паспорта
                    </TableHead>
                    <TableHead className="text-[#2B2318]">Тур</TableHead>
                    <TableHead className="text-[#2B2318]">Дата</TableHead>
                    <TableHead className="text-[#2B2318]">
                      Номер тур кода
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPilgrims.map((pilgrim, index) => (
                    <TableRow
                      key={pilgrim.id}
                      className="hover:bg-[#F5F1EA]/50"
                    >
                      <TableCell className="text-[#6B5435]">
                        {index + 1}
                      </TableCell>
                      <TableCell className="text-[#2B2318]">
                        {pilgrim.lastName}
                      </TableCell>
                      <TableCell className="text-[#2B2318]">
                        {pilgrim.firstName}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.middleName}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.passportNumber}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.tourName}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.tourDate}
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
              <p>
                {searchLastName || searchFirstName
                  ? "Паломники не найдены. Попробуйте изменить критерии поиска"
                  : "Введите фамилию или имя для поиска паломников"}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}