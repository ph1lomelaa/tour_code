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
          <h1 className="text-3xl mb-2 text-brand-ink">Паломники</h1>
          <p className="text-brand-text">
            Поиск паломников по фамилии и номеру паспорта
          </p>
        </div>

        {/* Search Filters */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-brand-line mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Поиск по фамилии */}
            <div>
              <label className="block text-sm mb-2 text-brand-ink">
                Фамилия
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-muted" />
                <Input
                  type="text"
                  value={searchLastName}
                  onChange={(e) => setSearchLastName(e.target.value)}
                  placeholder="Введите фамилию"
                  className="pl-10 bg-brand-cream border-brand-line focus:border-brand-accent"
                />
              </div>
            </div>

            {/* Поиск по номеру документа */}
            <div>
              <label className="block text-sm mb-2 text-brand-ink">
                Номер паспорта
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-muted" />
                <Input
                  type="text"
                  value={searchDocument}
                  onChange={(e) => setSearchDocument(e.target.value)}
                  placeholder="Введите номер паспорта"
                  className="pl-10 bg-brand-cream border-brand-line focus:border-brand-accent"
                />
              </div>
            </div>
          </div>

          {/* Results count */}
          <div className="mt-4 text-sm text-brand-text">
            Найдено паломников: {total}
          </div>
        </div>

        {/* Pilgrims Table */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-brand-line">
          <h2 className="mb-6 text-brand-ink">Список паломников</h2>

          {error ? (
            <div className="text-brand-alert">{error}</div>
          ) : isLoading ? (
            <div className="flex items-center justify-center h-40 text-brand-muted">
              <p>Загрузка...</p>
            </div>
          ) : pilgrims.length > 0 ? (
            <div className="border border-brand-line rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-brand-cream hover:bg-brand-cream">
                    <TableHead className="text-brand-ink">№</TableHead>
                    <TableHead className="text-brand-ink">Фамилия</TableHead>
                    <TableHead className="text-brand-ink">Имя</TableHead>
                    <TableHead className="text-brand-ink">
                      Номер паспорта
                    </TableHead>
                    <TableHead className="text-brand-ink">Тур код</TableHead>
                    <TableHead className="text-brand-ink">Пакет</TableHead>
                    <TableHead className="text-brand-ink">Тур</TableHead>
                    <TableHead className="text-brand-ink">Маршрут</TableHead>
                    <TableHead className="text-brand-ink">Период</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pilgrims.map((pilgrim, index) => (
                    <TableRow
                      key={pilgrim.id}
                      className="hover:bg-brand-cream/50"
                    >
                      <TableCell className="text-brand-text">
                        {(page - 1) * PAGE_SIZE + index + 1}
                      </TableCell>
                      <TableCell className="text-brand-ink">
                        {pilgrim.surname}
                      </TableCell>
                      <TableCell className="text-brand-ink">
                        {pilgrim.name}
                      </TableCell>
                      <TableCell className="text-brand-text">
                        {pilgrim.document || "-"}
                      </TableCell>
                      <TableCell className="text-brand-text">
                        {pilgrim.tour_code || "-"}
                      </TableCell>
                      <TableCell className="text-brand-text">
                        {pilgrim.package_name || "-"}
                      </TableCell>
                      <TableCell className="text-brand-text">
                        {pilgrim.tour_name || "-"}
                      </TableCell>
                      <TableCell className="text-brand-text">
                        {pilgrim.tour_route || "-"}
                      </TableCell>
                      <TableCell className="text-brand-text">
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
            <div className="flex items-center justify-center h-64 text-brand-muted">
              <p>
                {hasFilters
                  ? "Паломники не найдены. Попробуйте изменить критерии поиска"
                  : "Паломники пока отсутствуют"}
              </p>
            </div>
          )}

          {!isLoading && !error && totalPages > 0 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-brand-text">
                Страница {page} из {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="border-brand-line hover:bg-brand-cream"
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page <= 1}
                >
                  Назад
                </Button>
                <Button
                  variant="outline"
                  className="border-brand-line hover:bg-brand-cream"
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
