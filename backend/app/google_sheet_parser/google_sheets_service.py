
import logging
import time
from typing import List, Dict, Optional
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


class GoogleSheetsService:

    def __init__(self):
        self._client = None

    @property
    def client(self) -> gspread.Client:
        """Lazy loading клиента"""
        if self._client is None:
            try:
                creds = Credentials.from_service_account_file(
                    settings.GOOGLE_SHEETS_CREDENTIALS_FILE,
                    scopes=SCOPES
                )
                self._client = gspread.authorize(creds)
                logger.info("Google Sheets клиент подключен")
            except Exception as e:
                logger.error(f"Ошибка подключения к Google Sheets: {e}")
                raise
        return self._client

    def _api_call_with_retry(self, func, max_retries=3):
        """Вызов API с retry при 429 ошибке"""
        for attempt in range(max_retries):
            try:
                return func()
            except gspread.exceptions.APIError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s
                    logger.warning(f"Rate limit, ждём {wait}с...")
                    time.sleep(wait)
                else:
                    raise

    def get_all_spreadsheets(self) -> Dict[str, str]:
        try:
            result = self._api_call_with_retry(
                lambda: {ss.title: ss.id for ss in self.client.openall()}
            )
            logger.info(f"Найдено {len(result)} таблиц")
            return result
        except Exception as e:
            logger.error(f"Ошибка получения таблиц: {e}")
            return {}

    def get_sheet_names(self, spreadsheet_id: str) -> List[str]:
        try:
            result = self._api_call_with_retry(
                lambda: [ws.title for ws in self.client.open_by_key(spreadsheet_id).worksheets()]
            )
            return result
        except Exception as e:
            logger.error(f"Ошибка получения листов: {e}")
            return []

    def find_sheets_by_date(self, date_str: str) -> List[Dict]:
        date_normalized = self._normalize_date(date_str)
        target_tables = self._get_current_and_next_year_tables()

        results = []

        for table_name, table_id in target_tables.items():
            try:
                sheet_names = self.get_sheet_names(table_id)
                time.sleep(1)
                for sheet_name in sheet_names:
                    if self._sheet_matches_date(sheet_name, date_normalized):
                        parsed = self._parse_sheet_name(sheet_name)

                        if parsed:
                            results.append({
                                "spreadsheet_id": table_id,
                                "spreadsheet_name": table_name,
                                "sheet_name": sheet_name,
                                "date_start": parsed["date_start"],
                                "date_end": parsed["date_end"],
                                "days": parsed["days"],
                                "route": parsed["route"]
                            })

                            logger.info(f"Найден лист: {sheet_name} в таблице {table_name}")

            except Exception as e:
                logger.error(f"Ошибка обработки таблицы {table_name}: {e}")
                continue

        logger.info(f"Найдено {len(results)} листов для даты {date_str}")
        return results

    def _get_current_and_next_year_tables(self) -> Dict[str, str]:
        """Получить таблицы текущего и следующего года"""
        now = datetime.now()
        years = [str(now.year), str(now.year + 1)]

        all_tables = self.get_all_spreadsheets()

        target = {}
        for name, table_id in all_tables.items():
            if any(year in name for year in years):
                target[name] = table_id

        return target

    def _normalize_date(self, date_str: str) -> str:
        """Нормализует дату: 7.02 -> 07.02"""
        parts = date_str.strip().split(".")
        if len(parts) == 2:
            dd = parts[0].zfill(2)
            mm = parts[1].zfill(2)
            return f"{dd}.{mm}"
        return date_str

    def _sheet_matches_date(self, sheet_name: str, date_normalized: str) -> bool:
        """Проверяет, соответствует ли название листа дате"""
        parts = date_normalized.split(".")
        if len(parts) == 2:
            dd, mm = parts
            variants = [
                f"{dd}.{mm}",           # 07.03
                f"{int(dd)}.{mm}",      # 7.03
                f"{dd}.{int(mm)}",      # 07.3
                f"{int(dd)}.{int(mm)}"  # 7.3
            ]

            for variant in variants:
                if sheet_name.strip().startswith(variant):
                    return True

        return False

    def _parse_sheet_name(self, sheet_name: str) -> Optional[Dict]:
        try:
            # Паттерн 1: "17.02.2026-24.02.2026 ALA-JED"
            pattern1 = r'(\d{1,2}\.\d{1,2}\.\d{4})\s*[-–]\s*(\d{1,2}\.\d{1,2}\.\d{4})'
            match1 = re.search(pattern1, sheet_name)

            if match1:
                date_start_str = match1.group(1)
                date_end_str = match1.group(2)

                date_start = datetime.strptime(date_start_str, "%d.%m.%Y")
                date_end = datetime.strptime(date_end_str, "%d.%m.%Y")

                days = (date_end - date_start).days + 1
                route = self._extract_route(sheet_name)

                return {
                    "date_start": date_start_str,
                    "date_end": date_end_str,
                    "days": days,
                    "route": route
                }

            # Паттерн 2: "17.02-24.02 Ala-Jed/7d" (без года)
            pattern2 = r'(\d{1,2}\.\d{1,2})\s*[-–]\s*(\d{1,2}\.\d{1,2})'
            match2 = re.search(pattern2, sheet_name)

            if match2:
                date_start_short = match2.group(1)
                date_end_short = match2.group(2)

                now = datetime.now()
                year = now.year

                month_start = int(date_start_short.split(".")[1])
                if month_start < now.month:
                    year = now.year + 1

                date_start_str = f"{date_start_short}.{year}"
                date_end_str = f"{date_end_short}.{year}"

                try:
                    date_start = datetime.strptime(date_start_str, "%d.%m.%Y")
                    date_end = datetime.strptime(date_end_str, "%d.%m.%Y")

                    days = (date_end - date_start).days + 1
                    route = self._extract_route(sheet_name)

                    return {
                        "date_start": date_start_str,
                        "date_end": date_end_str,
                        "days": days,
                        "route": route
                    }
                except Exception as e:
                    logger.error(f"Ошибка парсинга дат: {e}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Ошибка парсинга листа '{sheet_name}': {e}")
            return None

    def _extract_route(self, text: str) -> Optional[str]:
        """Извлекает маршрут из текста: ALA-JED, ALA-MED, NQZ-JED, NQZ-MED"""
        routes = ["ALA-JED", "ALA-MED", "NQZ-JED", "NQZ-MED", "NQZ-ALA"]

        text_upper = text.upper()
        for route in routes:
            if route in text_upper:
                return route

        return None


# Синглтон
google_sheets_service = GoogleSheetsService()
