"""
Сервис для парсинга манифестов паломников из Excel файлов
"""
import logging
from typing import List, Dict
import pandas as pd
from io import BytesIO

logger = logging.getLogger(__name__)


class ManifestParser:
    """Парсер Excel манифестов"""

    def parse_manifest(self, file_content: bytes, filename: str) -> List[Dict]:
        """
        Парсит Excel манифест и извлекает паломников

        Args:
            file_content: содержимое Excel файла в байтах
            filename: имя файла для логирования

        Returns:
            [
                {
                    "surname": "NOKUSHEVA",
                    "name": "BAKYTGUL",
                    "document": "N13964983"
                },
                ...
            ]
        """
        try:
            # Читаем Excel из байтов
            df = pd.read_excel(BytesIO(file_content), sheet_name=0)

            logger.info(f"Парсинг манифеста {filename}: {len(df)} строк")

            pilgrims = []

            for idx, row in df.iterrows():
                # Пропускаем пустые строки
                if pd.isna(row.get('surname')) or pd.isna(row.get('document')):
                    continue

                surname = str(row['surname']).strip().upper()
                name = str(row.get('name', '')).strip().upper()
                document = str(row['document']).strip().upper()

                # Пропускаем если нет основных данных
                if not surname or not document:
                    continue

                pilgrims.append({
                    "surname": surname,
                    "name": name,
                    "document": document
                })

            logger.info(f"✅ Извлечено {len(pilgrims)} паломников из манифеста")
            return pilgrims

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга манифеста {filename}: {e}")
            raise ValueError(f"Не удалось распарсить манифест: {str(e)}")


# Синглтон
manifest_parser = ManifestParser()
