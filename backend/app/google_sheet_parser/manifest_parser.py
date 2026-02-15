"""
Сервис для парсинга манифестов паломников из Excel файлов
"""
import logging
from decimal import Decimal, InvalidOperation
import re
from typing import List, Dict, Optional
import pandas as pd
from io import BytesIO
from app.services.document_rules import normalize_document

logger = logging.getLogger(__name__)


class ManifestParser:

    def parse_manifest(self, file_content: bytes, filename: str) -> List[Dict]:
        try:
            df = pd.read_excel(BytesIO(file_content), sheet_name=0)

            logger.info(f"Парсинг манифеста {filename}: {len(df)} строк")

            columns_map = {str(col).strip().lower(): col for col in df.columns}

            surname_col = self._find_column(columns_map, ['surname', 'last name', 'lastname', 'фамилия'])
            excluded = {surname_col} if surname_col else set()
            name_col = self._find_column(columns_map, ['name', 'first name', 'firstname', 'имя'], exclude=excluded)
            full_name_col = self._find_column(columns_map, ['full name', 'first/last name', 'fio', 'фио'], exclude=excluded)
            document_col = self._find_column(
                columns_map,
                ['document number', 'document no', 'document', 'passport number', 'passport', 'паспорт'],
                exclude=excluded,
            )
            iin_col = self._find_column(columns_map, ['iin', 'иин', 'iin number', 'personal id'], exclude=excluded)

            if surname_col is None:
                raise ValueError("В манифесте не найдена колонка surname/last name")

            pilgrims = []

            for idx, row in df.iterrows():
                surname = self._to_text(row.get(surname_col)).upper()
                if not surname:
                    continue

                name = self._to_text(row.get(name_col)).upper() if name_col else ""
                if full_name_col and (not name or not surname):
                    full_name = self._to_text(row.get(full_name_col))
                    full_surname, full_name_name = self._split_full_name(full_name)
                    if not surname:
                        surname = full_surname.upper()
                    if not name:
                        name = full_name_name.upper()

                if surname and not name and " " in surname:
                    split_surname, split_name = self._split_full_name(surname)
                    if split_name:
                        surname = split_surname.upper()
                        name = split_name.upper()

                document = self._normalize_document(self._to_text(row.get(document_col))) if document_col else ""
                iin = self._normalize_iin(self._to_text(row.get(iin_col))) if iin_col else ""

                if not document and not iin and not name:
                    continue

                pilgrims.append({
                    "surname": surname,
                    "name": name,
                    "document": document,
                    "iin": iin,
                })

            logger.info(f"✅ Извлечено {len(pilgrims)} паломников из манифеста")
            return pilgrims

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга манифеста {filename}: {e}")
            raise ValueError(f"Не удалось распарсить манифест: {str(e)}")

    def _find_column(self, columns_map: Dict[str, str], aliases: List[str], exclude: Optional[set] = None) -> Optional[str]:
        excluded = exclude or set()
        normalized_columns = [
            (self._normalize_header(normalized), original)
            for normalized, original in columns_map.items()
            if original not in excluded
        ]

        for alias in aliases:
            alias_normalized = self._normalize_header(alias)
            for normalized, original in normalized_columns:
                if normalized == alias_normalized:
                    return original
                
        for alias in aliases:
            alias_normalized = self._normalize_header(alias)
            if not alias_normalized:
                continue
            alias_pattern = r'\b' + re.escape(alias_normalized).replace(r'\ ', r'\s+') + r'\b'
            for normalized, original in normalized_columns:
                if re.search(alias_pattern, normalized):
                    return original

        return None

    def _to_text(self, value) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    def _normalize_header(self, value: str) -> str:
        normalized = re.sub(r'[^a-z0-9а-яё]+', ' ', str(value).lower())
        return re.sub(r'\s+', ' ', normalized).strip()

    def _split_full_name(self, value: str) -> tuple[str, str]:
        normalized = re.sub(r'\s+', ' ', str(value or "").strip())
        if not normalized:
            return "", ""
        parts = normalized.split(" ")
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _normalize_document(self, value: str) -> str:
        cleaned = re.sub(r"[^\w]", "", value.upper().strip())
        return normalize_document(cleaned)

    def _normalize_iin(self, value: str) -> str:
        value = value.strip().replace(" ", "")
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


# Синглтон
manifest_parser = ManifestParser()
