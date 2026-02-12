import logging
from typing import List, Dict, Optional
import re
from app.services.google_sheets_service import google_sheets_service

logger = logging.getLogger(__name__)


class SheetPilgrimParser:
    def parse_sheet_pilgrims(
        self,
        spreadsheet_id: str,
        sheet_name: str
    ) -> List[Dict]:
        try:
            logger.info(f"Парсинг паломников из листа '{sheet_name}'")

            # Получаем данные листа
            client = google_sheets_service.client
            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)

            # Получаем все значения
            all_values = worksheet.get_all_values()

            if not all_values:
                logger.warning("Лист пуст")
                return []

            # Ищем заголовки
            header_row_idx = self._find_header_row(all_values)

            if header_row_idx is None:
                logger.warning("Не найдена строка с заголовками")
                return []

            headers = [str(h).strip().lower() for h in all_values[header_row_idx]]

            # Ищем индексы нужных колонок
            surname_idx = self._find_column_index(headers, ['surname', 'фамилия', 'lastname'])
            name_idx = self._find_column_index(headers, ['name', 'имя', 'firstname'])
            document_idx = self._find_column_index(headers, ['document', 'passport', 'паспорт', 'номер паспорта'])
            manager_idx = self._find_column_index(headers, ['manager', 'менеджер', 'manager name'])

            if surname_idx is None or document_idx is None:
                logger.error("Не найдены обязательные колонки (surname, document)")
                return []

            pilgrims = []

            # Парсим строки с данными
            for row_idx in range(header_row_idx + 1, len(all_values)):
                row = all_values[row_idx]

                if not row or len(row) <= max(surname_idx, document_idx):
                    continue

                surname = str(row[surname_idx]).strip().upper() if surname_idx < len(row) else ""
                name = str(row[name_idx]).strip().upper() if name_idx is not None and name_idx < len(row) else ""
                document = str(row[document_idx]).strip().upper() if document_idx < len(row) else ""
                manager = str(row[manager_idx]).strip() if manager_idx is not None and manager_idx < len(row) else ""

                # Пропускаем пустые строки
                if not surname or not document:
                    continue

                # Очищаем номер паспорта от лишних символов
                document = self._clean_document(document)

                if not document:
                    continue

                pilgrims.append({
                    "surname": surname,
                    "name": name,
                    "document": document,
                    "manager": manager
                })

            logger.info(f"✅ Извлечено {len(pilgrims)} паломников из листа")
            return pilgrims

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга листа: {e}")
            raise ValueError(f"Не удалось распарсить лист: {str(e)}")

    def _find_header_row(self, all_values: List[List]) -> Optional[int]:
        keywords = ['surname', 'name', 'document', 'passport', 'фамилия', 'имя', 'паспорт']

        for idx, row in enumerate(all_values[:20]):  # Ищем в первых 20 строках
            row_lower = [str(cell).strip().lower() for cell in row]

            # Если хотя бы 2 ключевых слова найдены
            matches = sum(1 for keyword in keywords if any(keyword in cell for cell in row_lower))

            if matches >= 2:
                return idx

        return None

    def _find_column_index(self, headers: List[str], possible_names: List[str]) -> Optional[int]:
        """Находит индекс колонки по возможным названиям"""
        for idx, header in enumerate(headers):
            for name in possible_names:
                if name in header:
                    return idx
        return None

    def _clean_document(self, document: str) -> str:
        """Очищает номер документа от лишних символов"""
        # Удаляем пробелы, дефисы, оставляем только буквы и цифры
        cleaned = re.sub(r'[^\w]', '', document)
        return cleaned


# Синглтон
sheet_pilgrim_parser = SheetPilgrimParser()
