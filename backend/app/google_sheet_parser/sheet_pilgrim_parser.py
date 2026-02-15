import logging
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple
import re
from app.google_sheet_parser.google_sheets_service import google_sheets_service
from app.services.document_rules import normalize_document

logger = logging.getLogger(__name__)
PACKAGE_HEADER_RE = re.compile(r'\d{1,2}\.\d{1,2}\s*[-–]\s*\d{1,2}\.\d{1,2}')
PACKAGE_KEYWORDS = ['niyet', 'hikma', 'izi', '4u', '4 u', '4 you', 'amal', 'aroya', 'aa', 'shohada', '7d', '10d']
CANCEL_KEYWORDS = ['отмена', 'cancel', 'cancelled', 'canceled', 'не едет', 'не летит']
LOG_PACKAGE_PILGRIMS = True


class SheetPilgrimParser:
    def parse_sheet_pilgrims(
        self,
        spreadsheet_id: str,
        sheet_name: str
    ) -> List[Dict]:
        try:
            logger.info(f"Парсинг паломников из листа '{sheet_name}'")

            all_values = self._get_sheet_values(spreadsheet_id, sheet_name)

            if not all_values:
                return []

            header_row_idx = self._find_header_row(all_values)

            if header_row_idx is None:
                logger.warning("Не найдена строка с заголовками")
                return []

            headers = [str(h).strip().lower() for h in all_values[header_row_idx]]
            col_map = self._build_column_map(headers)

            if not self._has_name_source(col_map):
                logger.error("Не найдены обязательные колонки с ФИО")
                return []

            pilgrims = self._parse_rows(
                all_values,
                header_row_idx + 1,
                len(all_values),
                col_map,
                require_room=False,
                require_meal=False,
            )

            logger.info(f"✅ Извлечено {len(pilgrims)} паломников из листа")
            return pilgrims

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга листа: {e}")
            raise ValueError(f"Не удалось распарсить лист: {str(e)}")

    # ==================== Новый метод (по пакетам) ====================

    def parse_sheet_by_packages(
        self,
        spreadsheet_id: str,
        sheet_name: str
    ) -> List[Dict]:
        try:
            logger.info(f"Парсинг по пакетам из листа '{sheet_name}'")

            all_values = self._get_sheet_values(spreadsheet_id, sheet_name)

            if not all_values:
                return []

            package_boundaries = self._find_package_boundaries(all_values)
            package_boundaries = self._prepend_leading_package_block(
                all_values,
                package_boundaries,
                sheet_name
            )

            if not package_boundaries:
                logger.warning("Пакеты не найдены, парсим как один блок")
                header_idx = self._find_header_row(all_values)
                if header_idx is None:
                    return []
                headers = [str(h).strip().lower() for h in all_values[header_idx]]
                col_map = self._build_column_map(headers)
                if not self._has_name_source(col_map):
                    return []
                pilgrims = self._parse_rows(
                    all_values,
                    header_idx + 1,
                    len(all_values),
                    col_map,
                    require_room=False,
                    require_meal=True,
                )
                return [{
                    "package_name": sheet_name,
                    "pilgrims": pilgrims,
                    "count": len(pilgrims)
                }]

            packages = []

            for pkg_name, start_row, end_row in package_boundaries:
                header_idx = self._find_header_row(all_values, start_row, min(start_row + 20, end_row))

                if header_idx is None:
                    logger.warning(f"Заголовок не найден в пакете '{pkg_name}'")
                    continue

                headers = [str(h).strip().lower() for h in all_values[header_idx]]
                col_map = self._build_column_map(headers)

                if not self._has_name_source(col_map):
                    logger.warning(f"Колонки с ФИО не найдены в пакете '{pkg_name}'")
                    continue

                pilgrims = self._parse_rows(
                    all_values,
                    header_idx + 1,
                    end_row,
                    col_map,
                    require_room=False,
                    require_meal=True,
                )

                if pilgrims:
                    packages.append({
                        "package_name": pkg_name,
                        "pilgrims": pilgrims,
                        "count": len(pilgrims)
                    })
                    logger.info(f"Пакет '{pkg_name}': {len(pilgrims)} паломников")
                    if LOG_PACKAGE_PILGRIMS:
                        self._log_package_pilgrims(pkg_name, pilgrims)

            logger.info(f"✅ Найдено {len(packages)} пакетов")
            return packages

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга по пакетам: {e}")
            raise ValueError(f"Не удалось распарсить лист по пакетам: {str(e)}")

    def _get_sheet_values(self, spreadsheet_id: str, sheet_name: str) -> List[List]:
        """Загружает все значения из листа"""
        client = google_sheets_service.client
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        all_values = worksheet.get_all_values()

        if not all_values:
            logger.warning("Лист пуст")
            return []

        return all_values

    def _find_package_boundaries(self, all_values: List[List]) -> List[tuple]:
        package_rows = []

        for idx, row in enumerate(all_values):
            row_text = ' '.join(str(cell) for cell in row[:5] if cell).strip()

            if not row_text:
                continue

            has_dates = bool(PACKAGE_HEADER_RE.search(row_text))
            if not has_dates:
                continue

            header_nearby = False
            for k in range(1, 6):
                check_idx = idx + k
                if check_idx < len(all_values):
                    if self._find_header_row(all_values, check_idx, check_idx + 1) is not None:
                        header_nearby = True
                        break

            if header_nearby:
                package_rows.append((row_text, idx))
                logger.info(f"Найден пакет в строке {idx}: '{row_text}'")

        boundaries = []
        for i, (name, start) in enumerate(package_rows):
            if i + 1 < len(package_rows):
                end = package_rows[i + 1][1]
            else:
                end = len(all_values)
            boundaries.append((name, start, end))

        return boundaries

    def _build_column_map(self, headers: List[str]) -> Dict[str, Optional[int]]:
        surname_idx = self._find_column_index(headers, ['surname', 'фамилия', 'lastname', 'last name'])
        exclude = {surname_idx} if surname_idx is not None else set()
        name_idx = self._find_column_index(headers, ['name', 'имя', 'firstname', 'first name'], exclude)

        return {
            "surname": surname_idx,
            "name": name_idx,
            "full_name": self._find_column_index(headers, ['first/last name', 'full name', 'fio', 'фио']),
            "document": self._find_column_index(headers, [
                'document number', 'document', 'passport', 'паспорт', 'номер паспорта', 'doc number'
            ]),
            "iin": self._find_column_index(headers, ['iin', 'иин', 'iin number', 'personal id']),
            "manager": self._find_column_index(headers, ['manager', 'менеджер', 'manager name']),
            "room_type": self._find_column_index(headers, [
                'type of room', 'room', 'комната', 'тип комнаты', 'тип'
            ]),
            "meal_type": self._find_column_index(headers, ['meal a day', 'meal', 'питание']),
            "comment": self._find_column_index(headers, ['comment', 'сomment', 'коммент', 'примеч']),
        }

    def _parse_rows(
        self,
        all_values: List[List],
        start_row: int,
        end_row: int,
        col_map: Dict[str, Optional[int]],
        require_room: bool = False,
        require_meal: bool = False,
    ) -> List[Dict]:
        surname_idx = col_map["surname"]
        name_idx = col_map["name"]
        full_name_idx = col_map["full_name"]
        document_idx = col_map["document"]
        iin_idx = col_map["iin"]
        manager_idx = col_map["manager"]
        room_idx = col_map["room_type"]
        meal_idx = col_map["meal_type"]
        comment_idx = col_map["comment"]

        pilgrims = []
        current_room_type = None
        current_meal_type = None

        if surname_idx is None and full_name_idx is None:
            return pilgrims

        required_col_indices = [idx for idx in [surname_idx, full_name_idx] if idx is not None]

        for row_idx in range(start_row, end_row):
            row = all_values[row_idx]

            if not row:
                continue

            if required_col_indices and len(row) <= max(required_col_indices):
                continue

            # Определяем тип комнаты (наследуется от предыдущей строки если пусто)
            if room_idx is not None and room_idx < len(row):
                cell_room = str(row[room_idx]).strip()
                if cell_room:
                    current_room_type = cell_room

            # Питание также наследуется от предыдущей строки
            if meal_idx is not None and meal_idx < len(row):
                cell_meal = str(row[meal_idx]).strip()
                if cell_meal:
                    current_meal_type = cell_meal

            surname_raw = str(row[surname_idx]).strip() if surname_idx is not None and surname_idx < len(row) else ""
            name_raw = str(row[name_idx]).strip() if name_idx is not None and name_idx < len(row) else ""
            full_name_raw = str(row[full_name_idx]).strip() if full_name_idx is not None and full_name_idx < len(row) else ""

            if full_name_raw:
                if not surname_raw:
                    surname_raw, full_name_name = self._split_full_name(full_name_raw)
                    if not name_raw:
                        name_raw = full_name_name
                elif not name_raw:
                    _, full_name_name = self._split_full_name(full_name_raw)
                    if full_name_name:
                        name_raw = full_name_name
            elif surname_raw and not name_raw and " " in surname_raw:
                parsed_surname, parsed_name = self._split_full_name(surname_raw)
                if parsed_name:
                    surname_raw = parsed_surname
                    name_raw = parsed_name

            surname = surname_raw.upper()
            name = name_raw.upper()
            document_raw = str(row[document_idx]).strip().upper() if document_idx is not None and document_idx < len(row) else ""
            iin_raw = str(row[iin_idx]).strip() if iin_idx is not None and iin_idx < len(row) else ""
            manager = str(row[manager_idx]).strip() if manager_idx is not None and manager_idx < len(row) else ""
            comment = str(row[comment_idx]).strip() if comment_idx is not None and comment_idx < len(row) else ""
            meal_type = current_meal_type or ""

            if require_room and not current_room_type:
                continue

            if require_meal and not meal_type:
                continue

            if self._is_cancelled_row(meal_type, comment, surname, name):
                continue

            if not self._is_probable_person(surname, name):
                continue

            document = self._normalize_document(document_raw)
            iin = self._clean_iin(iin_raw)

            # Для сравнения нужен хотя бы один устойчивый идентификатор,
            # в крайнем случае оставляем ФИО (если документ/IIN отсутствуют)
            if not document and not iin and not name:
                continue

            pilgrim = {
                "surname": surname,
                "name": name,
                "document": document,
                "iin": iin,
                "manager": manager,
                "meal_type": meal_type,
            }

            if room_idx is not None:
                pilgrim["room_type"] = current_room_type or ""

            pilgrims.append(pilgrim)

        return pilgrims

    def _find_header_row(self, all_values: List[List], start: int = 0, end: int = 20) -> Optional[int]:
        keywords = [
            'surname', 'name', 'document', 'passport', 'document number',
            'фамилия', 'имя', 'паспорт', 'last name', 'first name',
            'first/last name', 'iin', 'иин'
        ]

        for idx in range(start, min(end, len(all_values))):
            row = all_values[idx]
            row_lower = [str(cell).strip().lower() for cell in row]

            matches = sum(1 for keyword in keywords if any(keyword in cell for cell in row_lower))

            if matches >= 2:
                return idx

        return None

    def _find_column_index(self, headers: List[str], possible_names: List[str], exclude: set = None) -> Optional[int]:
        """Находит индекс колонки по возможным названиям"""
        skip = exclude or set()
        for idx, header in enumerate(headers):
            if idx in skip:
                continue
            for name in possible_names:
                if name in header:
                    return idx
        return None

    def _has_name_source(self, col_map: Dict[str, Optional[int]]) -> bool:
        return col_map.get("surname") is not None or col_map.get("full_name") is not None

    def _prepend_leading_package_block(
        self,
        all_values: List[List],
        boundaries: List[Tuple[str, int, int]],
        fallback_name: str,
    ) -> List[Tuple[str, int, int]]:
        """
        Иногда первый пакет не содержит ключевых слов (напр. 'акционный'),
        но его таблица находится до первого распознанного пакета.
        """
        if not boundaries:
            return boundaries

        first_start = boundaries[0][1]
        if first_start <= 0:
            return boundaries

        leading_header_idx = self._find_header_row(all_values, 0, first_start)
        if leading_header_idx is None or leading_header_idx >= first_start:
            return boundaries

        block_name = self._extract_leading_block_name(all_values, leading_header_idx, fallback_name)
        return [(block_name, 0, first_start)] + boundaries

    def _extract_leading_block_name(
        self,
        all_values: List[List],
        header_idx: int,
        fallback_name: str,
    ) -> str:
        for idx in range(header_idx - 1, -1, -1):
            row_text = ' '.join(str(cell) for cell in all_values[idx][:5] if cell).strip()
            if not row_text:
                continue
            if PACKAGE_HEADER_RE.search(row_text):
                return row_text
            if any(kw in row_text.lower() for kw in PACKAGE_KEYWORDS):
                return row_text

        return fallback_name

    def _split_full_name(self, full_name: str) -> Tuple[str, str]:
        normalized = re.sub(r'\s+', ' ', full_name).strip()
        if not normalized:
            return "", ""

        parts = normalized.split(" ")
        if len(parts) == 1:
            return parts[0], ""

        return parts[0], " ".join(parts[1:])

    def _is_cancelled_row(self, meal_type: str, comment: str, surname: str, name: str) -> bool:
        text = f"{meal_type} {comment} {surname} {name}".lower()
        return any(keyword in text for keyword in CANCEL_KEYWORDS)

    def _is_probable_person(self, surname: str, name: str) -> bool:
        if not surname:
            return False

        surname_clean = re.sub(r'\s+', ' ', surname).strip()
        name_clean = re.sub(r'\s+', ' ', name).strip()
        normalized_surname = surname_clean.upper()

        header_values = {
            "LAST NAME", "FIRST NAME", "SURNAME", "NAME",
            "FIRST/LAST NAME", "ФАМИЛИЯ", "ИМЯ"
        }
        if normalized_surname in header_values:
            return False

        if not re.search(r'[A-ZА-ЯЁ]', surname_clean, re.IGNORECASE):
            return False

        # Исключаем служебные строки вида 46064.0
        if re.fullmatch(r'[\d\W_]+', surname_clean):
            return False

        if name_clean.upper() in header_values:
            return False

        return True

    def _normalize_document(self, document: str) -> str:
        cleaned = self._clean_document(document).upper()
        return normalize_document(cleaned)

    def _clean_iin(self, value: str) -> str:
        value = str(value or "").strip().replace(" ", "")
        if not value:
            return ""

        upper_value = value.upper()

        if re.fullmatch(r'\d{10,13}', upper_value):
            return upper_value

        if re.fullmatch(r'\d+\.0+', upper_value):
            int_part = upper_value.split(".", 1)[0]
            return int_part if len(int_part) >= 10 else ""

        if "E" in upper_value:
            try:
                sci_as_int = str(int(Decimal(upper_value)))
                return sci_as_int if len(sci_as_int) >= 10 else ""
            except (InvalidOperation, ValueError):
                pass

        digits = re.sub(r'\D', '', upper_value)
        return digits if len(digits) >= 10 else ""

    def _log_package_pilgrims(self, package_name: str, pilgrims: List[Dict]) -> None:
        logger.info(f"Список паломников пакета '{package_name}':")
        for idx, pilgrim in enumerate(pilgrims, start=1):
            surname = pilgrim.get("surname", "")
            name = pilgrim.get("name", "")
            document = pilgrim.get("document", "") or "-"
            iin = pilgrim.get("iin", "") or "-"
            meal = pilgrim.get("meal_type", "") or "-"
            room = pilgrim.get("room_type", "") or "-"
            logger.info(
                f"  {idx:03d}. {surname} {name} | doc={document} | iin={iin} | meal={meal} | room={room}"
            )

    def _clean_document(self, document: str) -> str:
        """Очищает номер документа от лишних символов"""
        cleaned = re.sub(r'[^\w]', '', document)
        return cleaned


# Синглтон
sheet_pilgrim_parser = SheetPilgrimParser()
