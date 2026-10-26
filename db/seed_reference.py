"""
Начальное заполнение справочников значениями, которые раньше были зашиты
в код (CreateTourCode.tsx, partner_payload_builder.py, tours.py).
Таблица заполняется только если она пустая — повторный запуск ничего не меняет
и не возвращает удалённые через «Настройки» записи.
"""
import logging

from sqlalchemy.orm import Session

from .models import RefAirline, RefCountry, RefHotel, RefRoute, RefTouragent

logger = logging.getLogger(__name__)

AIRLINES = [
    ("KC", "Air Astana"),
    ("DV", "SCAT"),
    ("FZ", "Flydubai"),
    ("EK", "Emirates"),
    ("QR", "Qatar Airways"),
    ("THY", "Turkish Airlines"),
]

COUNTRIES = [
    ("Саудовская Аравия", "Saudi Arabia"),
    ("Казахстан", "Kazakhstan"),
    ("Катар", "Qatar"),
    ("Объединенные Арабские Эмираты", "United Arab Emirates"),
    ("Турция", "Turkey"),
]

HOTELS = [
    ("Hilton Makkah Convention Hotel", "Makkah"),
    ("Swissotel Makkah", "Makkah"),
    ("Pullman ZamZam Makkah", "Makkah"),
    ("Fairmont Makkah Clock Royal Tower", "Makkah"),
    ("Conrad Makkah", "Makkah"),
    ("Anjum Hotel Makkah", "Makkah"),
    ("Elaf Kinda Hotel", "Makkah"),
    ("Millennium Al Aqeeq Hotel", "Madinah"),
    ("Raffles Makkah", "Makkah"),
    ("Jumeirah Jabal Omar Makkah", "Makkah"),
    ("Dar Al Tawhid Makkah", "Makkah"),
    ("Dar Al Taqwa Madinah 5*", "Madinah"),
    ("Courtyard by Marriott", ""),
]

ROUTES = [
    ("ALA-DOH-JED", "Almaty"),
    ("JED-DOH-ALA", "Jeddah"),
    ("ALA-JED", "Almaty"),
    ("ALA-MED", "Almaty"),
    ("NQZ-JED", "Nur-Sultan"),
    ("NQZ-MED", "Nur-Sultan"),
    ("NQZ-ALA", "Nur-Sultan"),
    ("SCO-MED", "Shymkent"),
    ("SCO-JED", "Shymkent"),
    ("CIT-MED", "Shymkent"),
    ("CIT-JED", "Shymkent"),
    ("DXB-MED", "Dubai"),
    ("DXB-JED", "Dubai"),
]

# (название, БИН, по умолчанию)
TOURAGENTS = [
    ("Хикмет Travel", "080340019818", True),
    ("HICKMET PREMIUM", "240340000277", False),
    ("NIYET", "230940022228", False),
    ("AL-MARWA", "030340005591", False),
]


def seed_reference_data(db: Session) -> None:
    seeded = []

    if not db.query(RefAirline).first():
        db.add_all(RefAirline(code=c, name=n, sort_order=i) for i, (c, n) in enumerate(AIRLINES))
        seeded.append("airlines")
    if not db.query(RefCountry).first():
        db.add_all(RefCountry(name_ru=ru, name_en=en, sort_order=i) for i, (ru, en) in enumerate(COUNTRIES))
        seeded.append("countries")
    if not db.query(RefHotel).first():
        db.add_all(RefHotel(name=n, city=c, sort_order=i) for i, (n, c) in enumerate(HOTELS))
        seeded.append("hotels")
    if not db.query(RefRoute).first():
        db.add_all(RefRoute(code=c, departure_city=d, sort_order=i) for i, (c, d) in enumerate(ROUTES))
        seeded.append("routes")
    if not db.query(RefTouragent).first():
        db.add_all(
            RefTouragent(name=n, bin=b, is_default=d, sort_order=i)
            for i, (n, b, d) in enumerate(TOURAGENTS)
        )
        seeded.append("touragents")

    if seeded:
        db.commit()
        logger.info("Справочники заполнены начальными данными: %s", ", ".join(seeded))
