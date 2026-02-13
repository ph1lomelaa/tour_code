import { useEffect, useMemo, useState } from "react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Search } from "lucide-react";
import { getPilgrims, PilgrimListItem } from "../../src/lib/api/pilgrims";

const PAGE_SIZE = 20;

export function Pilgrims() {
  const [searchLastName, setSearchLastName] = useState("");
  const [searchDocument, setSearchDocument] = useState("");

  const [surnameFilter, setSurnameFilter] = useState("");
  const [documentFilter, setDocumentFilter] = useState("");

  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [pilgrims, setPilgrims] = useState<PilgrimListItem[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSurnameFilter(searchLastName.trim());
      setDocumentFilter(searchDocument.trim());
      setPage(1);
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [searchLastName, searchDocument]);

  useEffect(() => {
    let cancelled = false;

    const fetchPilgrims = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await getPilgrims({
          surname: surnameFilter || undefined,
          document: documentFilter || undefined,
          page,
          page_size: PAGE_SIZE,
        });

        if (cancelled) return;
        setPilgrims(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
      } catch (e) {
        if (cancelled) return;
        console.error("Error fetching pilgrims:", e);
        setPilgrims([]);
        setTotal(0);
        setTotalPages(0);
        setError("Не удалось загрузить паломников");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchPilgrims();

    return () => {
      cancelled = true;
    };
  }, [surnameFilter, documentFilter, page]);

  const hasFilters = useMemo(
    () => Boolean(searchLastName || searchDocument),
    [searchLastName, searchDocument]
  );

  return (
    <div className="p-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl mb-2 text-[#2B2318]">Паломники</h1>
          <p className="text-[#6B5435]">
            Поиск паломников по фамилии и номеру паспорта
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

            {/* Поиск по номеру документа */}
            <div>
              <label className="block text-sm mb-2 text-[#2B2318]">
                Номер паспорта
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8B6F47]" />
                <Input
                  type="text"
                  value={searchDocument}
                  onChange={(e) => setSearchDocument(e.target.value)}
                  placeholder="Введите номер паспорта"
                  className="pl-10 bg-[#F5F1EA] border-[#E5DDD0] focus:border-[#B8985F]"
                />
              </div>
            </div>
          </div>

          {/* Results count */}
          <div className="mt-4 text-sm text-[#6B5435]">
            Найдено паломников: {total}
          </div>
        </div>

        {/* Pilgrims Table */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-[#E5DDD0]">
          <h2 className="mb-6 text-[#2B2318]">Список паломников</h2>

          {error ? (
            <div className="text-red-600">{error}</div>
          ) : isLoading ? (
            <div className="flex items-center justify-center h-40 text-[#8B6F47]">
              <p>Загрузка...</p>
            </div>
          ) : pilgrims.length > 0 ? (
            <div className="border border-[#E5DDD0] rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#F5F1EA] hover:bg-[#F5F1EA]">
                    <TableHead className="text-[#2B2318]">№</TableHead>
                    <TableHead className="text-[#2B2318]">Фамилия</TableHead>
                    <TableHead className="text-[#2B2318]">Имя</TableHead>
                    <TableHead className="text-[#2B2318]">
                      Номер паспорта
                    </TableHead>
                    <TableHead className="text-[#2B2318]">Тур код</TableHead>
                    <TableHead className="text-[#2B2318]">Пакет</TableHead>
                    <TableHead className="text-[#2B2318]">Тур</TableHead>
                    <TableHead className="text-[#2B2318]">Маршрут</TableHead>
                    <TableHead className="text-[#2B2318]">Период</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pilgrims.map((pilgrim, index) => (
                    <TableRow
                      key={pilgrim.id}
                      className="hover:bg-[#F5F1EA]/50"
                    >
                      <TableCell className="text-[#6B5435]">
                        {(page - 1) * PAGE_SIZE + index + 1}
                      </TableCell>
                      <TableCell className="text-[#2B2318]">
                        {pilgrim.surname}
                      </TableCell>
                      <TableCell className="text-[#2B2318]">
                        {pilgrim.name}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.document || "-"}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.tour_code || "-"}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.package_name || "-"}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.tour_name || "-"}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.tour_route || "-"}
                      </TableCell>
                      <TableCell className="text-[#6B5435]">
                        {pilgrim.date_start && pilgrim.date_end
                          ? `${pilgrim.date_start} - ${pilgrim.date_end}`
                          : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-[#8B6F47]">
              <p>
                {hasFilters
                  ? "Паломники не найдены. Попробуйте изменить критерии поиска"
                  : "Паломники пока отсутствуют"}
              </p>
            </div>
          )}

          {!isLoading && !error && totalPages > 0 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-[#6B5435]">
                Страница {page} из {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page <= 1}
                >
                  Назад
                </Button>
                <Button
                  variant="outline"
                  className="border-[#E5DDD0] hover:bg-[#F5F1EA]"
                  onClick={() => setPage((prev) => prev + 1)}
                  disabled={page >= totalPages}
                >
                  Вперед
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
