import random
import colorsys
import re
from bull_project.bull_bot.core.google_sheets.client import (
    get_google_client,
    get_worksheet_by_title,
)
from bull_project.bull_bot.core.google_sheets.allocator import (
    check_has_train_column,
    find_package_row,
    find_headers_extended,
    get_room_size,
)

def row_col_to_a1(row, col):
    div = col
    string = ""
    while div > 0:
        module = (div - 1) % 26
        string = chr(65 + module) + string
        div = int((div - module) / 26)
    return string + str(row)

async def process_inf_passengers(ws, all_values, all_pilgrims, regular_pilgrims, saved_rows, cols, common_data, group_color, parent_row_override=None):
    """
    Обрабатывает INF паломников - вставляет для них строки под родителями.

    🔥 НОВАЯ ЛОГИКА: Все INF записываются ПОСЛЕ обычных паломников,
    даже если INF идет первым в списке - он будет записан последним и возьмет тип комнаты от первого обычного.

    Args:
        ws: Worksheet объект
        all_values: Все значения таблицы
        all_pilgrims: ВСЕ паломники в исходном порядке (включая INF)
        regular_pilgrims: Только обычные паломники (не-INF)
        saved_rows: Строки где записаны обычные паломники
        cols: Карта колонок
        common_data: Общие данные брони
        group_color: Цвет группы

    Returns:
        list: Финальный список строк для ВСЕХ паломников (включая INF)
    """
    print(f"\n🍼 Обработка INF паломников...")

    # Проверяем есть ли INF/CHD паломники
    special_count = sum(1 for p in all_pilgrims if p.get('is_infant', False) or p.get('is_child', False))
    if special_count == 0:
        print(f"   ℹ️ INF/CHD паломников нет, возвращаем исходные строки")
        return saved_rows

    print(f"   Найдено INF/CHD паломников: {special_count}")

    # 🔥 НОВЫЙ ПОДХОД: Создаем карту индекс в all_pilgrims -> строка в таблице (только для обычных)
    pilgrim_idx_to_row = {}
    regular_idx = 0

    for i, pilgrim in enumerate(all_pilgrims):
        is_inf = pilgrim.get('is_infant', False)
        is_chd = pilgrim.get('is_child', False)
        if not is_inf and not is_chd:
            pilgrim_idx_to_row[i] = saved_rows[regular_idx]
            regular_idx += 1

    print(f"   Карта обычных паломников: {pilgrim_idx_to_row}")

    # Результирующий список строк для ВСЕХ паломников
    final_rows = [None] * len(all_pilgrims)

    # Заполняем строки для обычных паломников
    for idx, row in pilgrim_idx_to_row.items():
        final_rows[idx] = row
        print(f"   ✅ Обычный паломник #{idx+1}: строка {row}")

    # 🔥 Обрабатываем INF паломников - ПОСЛЕ всех обычных
    # Сортируем по индексу чтобы обрабатывать в порядке от конца к началу
    # (чтобы вставки не сдвигали еще необработанных)
    inf_indices = [
        (i, p)
        for i, p in enumerate(all_pilgrims)
        if p.get('is_infant', False) or p.get('is_child', False)
    ]

    # Обрабатываем INF в обратном порядке (от конца к началу)
    for i, pilgrim in reversed(inf_indices):
        is_inf = pilgrim.get('is_infant', False)
        is_chd = pilgrim.get('is_child', False)
        label = "INF" if is_inf else "CHD" if is_chd else "PAX"
        print(f"\n   🍼 INF/CHD паломник #{i+1} (из {len(all_pilgrims)}): {label}")

        # Ищем ближайшего обычного паломника ПЕРЕД этим INF
        parent_idx = None
        for j in range(i - 1, -1, -1):
            if not (all_pilgrims[j].get('is_infant', False) or all_pilgrims[j].get('is_child', False)):
                parent_idx = j
                break

        # Если не нашли обычного паломника перед INF, берем первого обычного паломника
        if parent_idx is None:
            print(f"      INF идет первым, используем первого обычного паломника")
            # Находим первого обычного паломника
            for j in range(len(all_pilgrims)):
                if not (all_pilgrims[j].get('is_infant', False) or all_pilgrims[j].get('is_child', False)):
                    parent_idx = j
                    break

        if parent_idx is None:
            if parent_row_override:
                parent_row = parent_row_override
                print(f"      ✅ Используем родителя по specific_row: строка {parent_row}")
            else:
                print(f"      ⚠️ Нет обычных паломников вообще - пропускаем INF")
                continue
        else:
            parent_row = pilgrim_idx_to_row[parent_idx]
            print(f"      Родитель: паломник #{parent_idx+1}, строка {parent_row}")

        def _get_cell_value(row_idx: int, col_zero_based: int) -> str:
            if row_idx <= 0:
                return ""
            if row_idx - 1 >= len(all_values):
                return ""
            row = all_values[row_idx - 1]
            if col_zero_based >= len(row):
                return ""
            return str(row[col_zero_based] or "").strip()

        def _col_letter(col_1_based: int) -> str:
            # row_col_to_a1(1, col) => "D1"
            return re.sub(r"\d+", "", row_col_to_a1(1, col_1_based))

        try:
            # Вставляем новую строку после parent_row
            new_row_idx = parent_row + 1

            # КРИТИЧНО: Вставляем пустую строку
            ws.insert_row(values=[""] * 50, index=new_row_idx)
            print(f"      ✅ Вставлена пустая строка {new_row_idx}")

            # Подготавливаем данные для INF/CHD паломника
            infant_data = {**common_data, **pilgrim}
            if is_chd:
                infant_data['meal_type'] = 'CHD'
            else:
                infant_data['meal_type'] = 'INF'
            # На всякий случай: менеджер должен быть одинаковым для всех строк группы (включая INF)
            infant_data['manager_name_text'] = common_data.get('manager_name_text', infant_data.get('manager_name_text', ''))

            # Записываем данные младенца
            updates_infant = []
            price_tasks_infant = []
            _prepare_updates(updates_infant, price_tasks_infant, new_row_idx, cols, infant_data)

            # 🔥 Записываем "INF/CHD" в колонку "№"
            if 'num' in cols:
                num_col_a1 = row_col_to_a1(new_row_idx, cols['num'] + 1)
                updates_infant.append({'range': num_col_a1, 'values': [[label]]})
                print(f"      ✅ Записали '{label}' в колонку №: {num_col_a1}")

            # Применяем обновления
            if updates_infant:
                ws.batch_update(updates_infant)
                print(f"      ✅ Данные младенца записаны")

            # 🔥 ОБЪЕДИНЯЕМ ячейку типа комнаты по вертикали с родителем
            if 'room' in cols:
                room_col_idx = cols['room'] + 1
                col_letter = _col_letter(room_col_idx)

                # Частый кейс: тип комнаты уже был объединён на несколько строк (QUAD/TRPL/DBL),
                # и вставленная строка не попадает в существующий merge. Тогда нужно расширить merge:
                # unmerge старого диапазона -> merge с +1 строкой.
                room_col_zero = cols['room']
                start_row = parent_row
                while start_row > 1 and _get_cell_value(start_row, room_col_zero) == "":
                    start_row -= 1

                room_value = _get_cell_value(start_row, room_col_zero)
                room_size = get_room_size(room_value) if room_value else 1
                end_row = start_row + max(1, room_size) - 1
                if parent_row > end_row:
                    end_row = parent_row

                new_end_row = max(end_row + 1, new_row_idx)
                old_range = f"{col_letter}{start_row}:{col_letter}{end_row}"
                new_range = f"{col_letter}{start_row}:{col_letter}{new_end_row}"

                try:
                    ws.unmerge_cells(old_range)
                except Exception:
                    pass

                try:
                    ws.merge_cells(new_range, merge_type='MERGE_ALL')
                    print(f"      ✅ Объединены ячейки типа комнаты: {new_range}")
                except Exception as e:
                    print(f"      ⚠️ Не удалось объединить ячейки: {e}")

            # Окрашиваем имя/фамилию младенца тем же цветом что и группа
            for key in ("last_name", "first_name"):
                if key in cols:
                    a1 = row_col_to_a1(new_row_idx, cols[key] + 1)
                    try:
                        ws.format(a1, {"backgroundColor": group_color, "textFormat": {"bold": False}})
                    except: pass

            # Сохраняем строку младенца в карте и в final_rows
            final_rows[i] = new_row_idx
            print(f"      ✅ INF паломник #{i+1} записан в строку {new_row_idx}")

            # 🔥 ВАЖНО: После вставки строки все последующие строки сдвигаются вниз!
            # Обновляем карту pilgrim_idx_to_row для всех паломников после вставленной строки
            for idx, row in pilgrim_idx_to_row.items():
                if row >= new_row_idx:
                    pilgrim_idx_to_row[idx] = row + 1
                    if final_rows[idx] is not None:
                        final_rows[idx] = row + 1

        except Exception as e:
            print(f"      ❌ Ошибка вставки строки для INF: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n📊 Финальные строки для всех паломников: {final_rows}")
    return final_rows

async def save_group_booking(group_data: list, common_data: dict, placement_mode: str, specific_row=None, is_share=False):
    from bull_project.bull_bot.core.google_sheets.allocator import find_best_slot_for_group

    client = get_google_client()
    if not client:
        print("❌ Google client не инициализирован (get_google_client вернул None)")
        return []

    sheet_id = common_data.get('table_id')
    sheet_name = common_data.get('sheet_name')
    target_pkg = common_data['package_name']
    target_room = common_data['room_type']

    try:
        ss = client.open_by_key(sheet_id)
        ws = get_worksheet_by_title(ss, sheet_name)
        all_values = ws.get_all_values()

        saved_rows = []
        updates = []
        cols = None
        merge_tasks = []
        color_tasks = []
        price_tasks = []

        # 🔥 НОВАЯ ЛОГИКА: Разделяем паломников на обычных и INF
        regular_pilgrims = []  # Не-INF паломники (для размещения)
        all_pilgrims = []  # ВСЕ паломники в исходном порядке

        print(f"\n🔍 DEBUG: Проверка INF/CHD флагов для каждого паломника:")
        for idx, person in enumerate(group_data):
            is_inf = person.get('is_infant', False)
            is_chd = person.get('is_child', False)
            name = f"{person.get('Last Name', 'N/A')} {person.get('First Name', 'N/A')}"
            print(f"   Паломник {idx+1}: {name}")
            print(f"      is_infant: {is_inf} (тип: {type(is_inf)})")
            print(f"      is_child: {is_chd} (тип: {type(is_chd)})")
            all_pilgrims.append(person)
            if not is_inf and not is_chd:
                regular_pilgrims.append(person)

        print(f"\n📊 Обработка группы:")
        print(f"   Всего паломников: {len(all_pilgrims)}")
        print(f"   Обычных (для размещения): {len(regular_pilgrims)}")
        print(f"   INF/CHD (без места): {len(all_pilgrims) - len(regular_pilgrims)}")

        # Пастельный цвет для всей группы (один цвет на всех)
        seed_base = "".join([
            common_data.get("package_name", ""),
            common_data.get("room_type", ""),
            str(len(regular_pilgrims))  # 🔥 Используем количество обычных паломников
        ])
        rnd = random.Random(seed_base)
        h = rnd.random()
        s = 0.35
        v = 0.95
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        group_color = {"red": r, "green": g, "blue": b}

        # 🔥 ИСПРАВЛЕНИЕ: Используем групповое размещение для ОБЫЧНЫХ паломников (не-INF)
        if not specific_row and len(regular_pilgrims) > 0:
            # Используем функцию группового размещения только для обычных паломников
            saved_rows = find_best_slot_for_group(
                all_values,
                target_pkg,
                regular_pilgrims,  # 🔥 Передаем только не-INF паломников
                target_room,
                placement_mode
            )

            if not saved_rows or len(saved_rows) != len(regular_pilgrims):
                print(f"❌ Групповое размещение вернуло неполный список строк")
                print(f"   Ожидалось: {len(regular_pilgrims)}, получено: {len(saved_rows)}")
                return []

            # Получаем колонки для записи данных
            pkg_row = find_package_row(all_values, target_pkg)
            if pkg_row is not None:
                for r in range(pkg_row, min(pkg_row + 15, len(all_values))):
                    cols = find_headers_extended(all_values[r])
                    if cols: break

            if not cols:
                print(f"❌ Не найдены заголовки для пакета {target_pkg}")
                return []

            # Записываем данные для каждого ОБЫЧНОГО паломника
            for i, (person_passport, row_idx) in enumerate(zip(regular_pilgrims, saved_rows)):
                full_data = {**common_data, **person_passport}
                _prepare_updates(updates, price_tasks, row_idx, cols, full_data)
                # Планируем окраску имени/фамилии для группы (если в группе > 1 человека, включая INF)
                if len(all_pilgrims) > 1:
                    for key in ("last_name", "first_name"):
                        if key in cols:
                            a1 = row_col_to_a1(row_idx, cols[key] + 1)
                            color_tasks.append(a1)

        elif specific_row:
            # Ручное размещение: размещаем только обычных, INF/CHD вставляем ниже
            pkg_row = find_package_row(all_values, target_pkg)
            if pkg_row is not None:
                for r in range(pkg_row, min(pkg_row + 15, len(all_values))):
                    cols = find_headers_extended(all_values[r])
                    if cols: break
            if not cols: return []

            for i, person_passport in enumerate(regular_pilgrims):
                row_idx = specific_row + i
                saved_rows.append(row_idx)
                full_data = {**common_data, **person_passport}
                _prepare_updates(updates, price_tasks, row_idx, cols, full_data)
                # Планируем окраску имени/фамилии для группы (если в группе > 1 человека, включая INF)
                if len(all_pilgrims) > 1:
                    for key in ("last_name", "first_name"):
                        if key in cols:
                            a1 = row_col_to_a1(row_idx, cols[key] + 1)
                            color_tasks.append(a1)
        else:
            print(f"❌ Пустой список паломников")
            return []

        if updates: ws.batch_update(updates)
        # Применяем окраску имен/фамилий (один цвет на группу)
        for a1 in color_tasks:
            try:
                ws.format(a1, {"backgroundColor": group_color, "textFormat": {"bold": False}})
            except Exception as e:
                print(f"⚠️ Не удалось окрасить {a1}: {e}")
        # Форматируем цену и оплату
        for row_idx, col_idx in price_tasks:
            a1 = row_col_to_a1(row_idx, col_idx)
            try:
                ws.format(a1, {"numberFormat": {"type": "CURRENCY", "pattern": "[$$]#,##0"}})
            except Exception as e:
                print(f"⚠️ Не удалось применить формат цены для {a1}: {e}")
        if merge_tasks:
            for m_range in merge_tasks:
                try: ws.merge_cells(m_range, merge_type='MERGE_ALL')
                except: pass

        # 🔥 ОБРАБОТКА INF ПАЛОМНИКОВ - вставка строк под родителями
        parent_row_override = specific_row if specific_row and len(regular_pilgrims) == 0 else None
        final_rows = await process_inf_passengers(
            ws, all_values, all_pilgrims, regular_pilgrims, saved_rows,
            cols, common_data, group_color, parent_row_override=parent_row_override
        )

        return final_rows

    except Exception as e:
        print(f"❌ Save error: {e}")
        import traceback
        traceback.print_exc()
        return []

def do_transform(ws, updates, merge_tasks, all_values, start_idx, r_col, col_letter, rows_count, values, merges):
    range_str = f"{col_letter}{start_idx}:{col_letter}{start_idx + rows_count - 1}"
    try: ws.unmerge_cells(range_str)
    except: pass

    updates.append({'range': range_str, 'values': values})

    for m_start, m_end in merges:
        merge_tasks.append(f"{col_letter}{start_idx + m_start}:{col_letter}{start_idx + m_end}")

    # Обновляем память бота (Тип комнаты)
    for k in range(rows_count):
        if start_idx - 1 + k < len(all_values):
            all_values[start_idx - 1 + k][r_col] = values[k][0]

def _prepare_updates(updates_list, price_tasks, row_idx, cols, data):
    # Используем правильные ключи, которые приходят из паспортных данных

    # 🔥 ЛОГИКА CHD: Если паломник помечен как CHD, меняем тип питания на "CHD"
    meal_type = data.get('meal_type', '')
    is_child = data.get('is_child', False)
    if is_child:
        meal_type = 'CHD'
        print(f"   🧒 CHD: meal_type установлен в 'CHD' для строки {row_idx}")

    mapping = {
        'last_name': data.get('Last Name', '') or data.get('guest_last_name', ''),
        'first_name': data.get('First Name', '') or data.get('guest_first_name', ''),
        'gender': data.get('Gender', '') or data.get('gender', ''),
        'dob': data.get('Date of Birth', '') or data.get('date_of_birth', ''),
        'doc_num': data.get('Document Number', '') or data.get('passport_num', ''),
        'doc_exp': data.get('Document Expiration', '') or data.get('passport_expiry', ''),
        'iin': data.get('IIN', '') or data.get('guest_iin', ''),
        'visa': data.get('visa_status', ''),
        'avia': data.get('avia', ''),
        'meal': meal_type,  # 🔥 Используем meal_type с учетом CHD
        'price': data.get('price', ''),
        'amount_paid': data.get('amount_paid', ''),
        'exchange_rate': data.get('exchange_rate', ''),
        'discount': data.get('discount', ''),
        'manager': data.get('manager_name_text', ''),
        'comment': data.get('comment', ''),
        'client_phone': data.get('client_phone', ''),
        'train': data.get('train', ''),
        'region': data.get('region', ''),
        'source': data.get('source', '')
    }

    # Отладка для train - проверяем есть ли колонка в таблице
    if "train" in mapping and "train" not in cols:
        print(f"⚠️ TRAIN: Колонка 'train' НЕ найдена в таблице! Доступные колонки: {list(cols.keys())}")
    elif "train" in mapping and "train" in cols:
        print(f"✅ TRAIN: Колонка 'train' найдена в таблице (индекс {cols['train']}), значение = '{mapping.get('train')}'")

    for col_key, value in mapping.items():
        if col_key in cols:
            val_str = str(value).strip()
            if not val_str or val_str in ["-", "skip", "None"]:
                # Отладка для train
                if col_key == "train":
                    print(f"⚠️ TRAIN пропущен: значение = '{val_str}'")
                continue
            # Отладка для train
            if col_key == "train":
                print(f"✅ TRAIN будет записан: значение = '{val_str}'")
            # Цена и оплата — записываем как число и отмечаем для форматирования
            if col_key in ("price", "amount_paid"):
                clean = val_str.replace("$", "").replace(" ", "").replace(",", "")
                try:
                    num_val = float(clean)
                    price_tasks.append((row_idx, cols[col_key] + 1))
                    updates_list.append({'range': f"{row_col_to_a1(row_idx, cols[col_key] + 1)}", 'values': [[num_val]]})
                except:
                    updates_list.append({'range': f"{row_col_to_a1(row_idx, cols[col_key] + 1)}", 'values': [[val_str]]})
            else:
                updates_list.append({'range': f"{row_col_to_a1(row_idx, cols[col_key] + 1)}", 'values': [[val_str]]})

async def save_booking_smart(booking_data):
    passport_data = {
        'Last Name': booking_data.get('last_name'), 'First Name': booking_data.get('first_name'),
        'Gender': booking_data.get('gender'), 'Date of Birth': booking_data.get('dob'),
        'Document Number': booking_data.get('passport_num'), 'Document Expiration': booking_data.get('passport_exp')
    }
    rows = await save_group_booking([passport_data], booking_data, 'separate')
    return rows[0] if rows else False

async def check_train_exists(sheet_id, sheet_name, package_name):
    client = get_google_client()
    if not client: return False
    try:
        ss = client.open_by_key(sheet_id); ws = get_worksheet_by_title(ss, sheet_name); all_values = ws.get_all_values()
        return check_has_train_column(all_values, package_name)
    except: return False

async def clear_booking_in_sheets(sheet_id, sheet_name, row_number, package_name, expected_guest_name=None):
    """
    Очищает данные брони из Google Sheets.
    🎨 Также убирает цветную окраску с ячеек имени и фамилии.

    Args:
        sheet_id: ID таблицы Google Sheets
        sheet_name: Название листа
        row_number: Номер строки для очистки
        package_name: Название пакета
        expected_guest_name: Ожидаемое имя гостя (формат: "Фамилия Имя").
                            Если указано, проверяется совпадение перед удалением.

    Returns:
        bool: True если очистка успешна, False при ошибке или несовпадении имени
    """
    client = get_google_client()
    if not client or not row_number:
        return False

    try:
        ss = client.open_by_key(sheet_id)
        ws = get_worksheet_by_title(ss, sheet_name)
        all_values = ws.get_all_values()

        # Находим колонки
        pkg_row = find_package_row(all_values, package_name)
        cols = None
        if pkg_row is not None:
            for r in range(pkg_row, min(pkg_row + 30, len(all_values))):
                cols = find_headers_extended(all_values[r])
                if cols:
                    break

        if not cols:
            return False

        # 🔒 ПРОВЕРКА БЕЗОПАСНОСТИ: Проверяем, что в строке нужный человек
        if expected_guest_name:
            actual_last_name = ""
            actual_first_name = ""

            if 'last_name' in cols and row_number <= len(all_values):
                actual_last_name = all_values[row_number - 1][cols['last_name']].strip()

            if 'first_name' in cols and row_number <= len(all_values):
                actual_first_name = all_values[row_number - 1][cols['first_name']].strip()

            actual_name = f"{actual_last_name} {actual_first_name}".strip()
            expected_name = expected_guest_name.strip()

            # 🔥 Нормализуем оба имени: убираем доп. пробелы, приводим к нижнему регистру
            actual_name_normalized = " ".join(actual_name.split()).lower()
            expected_name_normalized = " ".join(expected_name.split()).lower()

            if actual_name_normalized != expected_name_normalized:
                print(f"⚠️ ВНИМАНИЕ: В строке {row_number} находится другой человек!")
                print(f"   Ожидали: '{expected_name}' (нормализовано: '{expected_name_normalized}')")
                print(f"   Нашли: '{actual_name}' (нормализовано: '{actual_name_normalized}')")
                print(f"   ❌ Очистка отменена для безопасности")
                return False
            else:
                print(f"   ✅ Проверка имени пройдена: '{actual_name}' == '{expected_name}'")

        # Очищаем данные
        fields_to_clear = ['last_name', 'first_name', 'gender', 'dob', 'doc_num', 'doc_exp', 'price', 'comment', 'manager', 'train', 'client_phone']
        updates = []
        for key in fields_to_clear:
            if key in cols:
                updates.append({'range': f"{row_col_to_a1(row_number, cols[key] + 1)}", 'values': [['']]})

        if updates:
            ws.batch_update(updates)

        # 🎨 УБИРАЕМ ЦВЕТНУЮ ОКРАСКУ с ячеек имени и фамилии
        print(f"   🧹 Очищаем окраску ячеек в строке {row_number}...")

        # Белый фон (по умолчанию)
        white_format = {
            "backgroundColor": {
                "red": 1.0,
                "green": 1.0,
                "blue": 1.0
            },
            "textFormat": {
                "bold": False
            }
        }

        # Очищаем last_name и first_name
        for key in ['last_name', 'first_name']:
            if key in cols:
                cell = row_col_to_a1(row_number, cols[key] + 1)
                try:
                    ws.format(cell, white_format)
                    print(f"      ✅ Окраска убрана: {cell}")
                except Exception as e:
                    print(f"      ⚠️ Не удалось очистить окраску {cell}: {e}")

        print(f"   ✅ Бронь очищена и окраска убрана")
        return True

    except Exception as e:
        print(f"❌ Ошибка очистки брони: {e}")
        return False


async def find_pilgrim_in_package(sheet_id, sheet_name, package_name, guest_name):
    """
    Ищет паломника по имени во всём пакете.

    Args:
        sheet_id: ID таблицы Google Sheets
        sheet_name: Название листа
        package_name: Название пакета
        guest_name: Имя для поиска (формат: "Фамилия Имя")

    Returns:
        list: Список найденных совпадений [(row_number, actual_name), ...]
    """
    from bull_project.bull_bot.core.google_sheets.allocator import get_package_block

    client = get_google_client()
    if not client:
        print("❌ Google client не инициализирован")
        return []

    try:
        ss = client.open_by_key(sheet_id)
        ws = get_worksheet_by_title(ss, sheet_name)
        all_values = ws.get_all_values()

        # Находим блок пакета
        start_row, end_row, cols = get_package_block(all_values, package_name)
        if not cols or start_row is None:
            print(f"❌ Не найден блок пакета {package_name}")
            return []

        # Нормализуем искомое имя
        expected_normalized = " ".join(guest_name.strip().split()).lower()
        print(f"🔍 Ищем паломника '{guest_name}' в пакете {package_name} (строки {start_row+1}-{end_row+1})")

        matches = []

        # Ищем по всем строкам пакета
        for row_idx in range(start_row, end_row + 1):
            if row_idx >= len(all_values):
                break

            row = all_values[row_idx]

            # Получаем имя из этой строки
            actual_last_name = ""
            actual_first_name = ""

            if 'last_name' in cols and cols['last_name'] < len(row):
                actual_last_name = row[cols['last_name']].strip()

            if 'first_name' in cols and cols['first_name'] < len(row):
                actual_first_name = row[cols['first_name']].strip()

            # Пропускаем пустые строки
            if not actual_last_name and not actual_first_name:
                continue

            actual_name = f"{actual_last_name} {actual_first_name}".strip()
            actual_normalized = " ".join(actual_name.split()).lower()

            # Проверяем совпадение
            if actual_normalized == expected_normalized:
                row_number = row_idx + 1  # +1 потому что Google Sheets считает с 1
                print(f"   ✅ Найдено точное совпадение в строке {row_number}: '{actual_name}'")
                matches.append((row_number, actual_name))

        if not matches:
            print(f"   ❌ Паломник '{guest_name}' не найден в пакете")
        else:
            print(f"   📋 Всего найдено совпадений: {len(matches)}")

        return matches

    except Exception as e:
        print(f"❌ Ошибка поиска паломника: {e}")
        import traceback
        traceback.print_exc()
        return []


def find_last_content_row(all_values):
    """Находит последнюю строку с содержимым на листе"""
    for r in range(len(all_values) - 1, -1, -1):
        row_text = "".join([str(c).strip() for c in all_values[r]])
        if len(row_text) > 2:  # Есть какой-то контент
            return r + 1  # +1 потому что индексы с 0
    return len(all_values)

async def write_cancelled_booking_red(sheet_id, sheet_name, package_name, guest_name):
    from bull_project.bull_bot.core.google_sheets.allocator import get_package_block
    client = get_google_client()
    if not client:
        print("❌ Google client не инициализирован")
        return False

    try:
        ss = client.open_by_key(sheet_id)
        ws = get_worksheet_by_title(ss, sheet_name)
        all_values = ws.get_all_values()

        # Находим блок пакета (нужно для получения колонки)
        _, _, cols = get_package_block(all_values, package_name)
        if not cols:
            print(f"❌ Не найден блок пакета {package_name}")
            return False

        # 🔥 НАХОДИМ ПОСЛЕДНЮЮ СТРОКУ НА ВСЕМ ЛИСТЕ
        last_row = find_last_content_row(all_values)
        # Отступаем 15 строк от конца ВСЕГО листа
        cancelled_row = last_row + 15

        print(f"📝 Записываем отмену в строку {cancelled_row} (последняя строка листа: {last_row})")

        # Находим колонку для записи имени
        name_col = cols.get('last_name')
        if not name_col:
            print("❌ Не найдена колонка для имени")
            return False

        # Записываем имя
        cell_range = row_col_to_a1(cancelled_row, name_col + 1)
        ws.update(cell_range, [[f"❌ ОТМЕНЕНО: {guest_name}"]])

        # Форматируем красным цветом
        ws.format(cell_range, {
            "backgroundColor": {
                "red": 1.0,
                "green": 0.8,
                "blue": 0.8
            },
            "textFormat": {
                "foregroundColor": {
                    "red": 0.8,
                    "green": 0.0,
                    "blue": 0.0
                },
                "fontSize": 11,
                "bold": True
            }
        })

        print(f"✅ Отмена записана красным в строку {cancelled_row}")
        return True

    except Exception as e:
        print(f"❌ Ошибка записи отмены: {e}")
        import traceback
        traceback.print_exc()
        return False

async def write_rescheduled_booking_red(sheet_id, sheet_name, package_name, guest_name):
    """Записывает перенос красным цветом внизу блока пакета"""
    from bull_project.bull_bot.core.google_sheets.allocator import get_package_block
    client = get_google_client()
    if not client:
        print("❌ Google client не инициализирован")
        return False

    try:
        ss = client.open_by_key(sheet_id)
        ws = get_worksheet_by_title(ss, sheet_name)
        all_values = ws.get_all_values()

        # Находим блок пакета (нужно для получения колонки)
        _, _, cols = get_package_block(all_values, package_name)
        if not cols:
            print(f"❌ Не найден блок пакета {package_name}")
            return False

        # 🔥 НАХОДИМ ПОСЛЕДНЮЮ СТРОКУ НА ВСЕМ ЛИСТЕ
        last_row = find_last_content_row(all_values)
        # Отступаем 15 строк от конца ВСЕГО листа
        rescheduled_row = last_row + 15

        print(f"📝 Записываем перенос в строку {rescheduled_row} (последняя строка листа: {last_row})")

        # Находим колонку для записи имени
        name_col = cols.get('last_name')
        if not name_col:
            print("❌ Не найдена колонка для имени")
            return False

        # Записываем имя
        cell_range = row_col_to_a1(rescheduled_row, name_col + 1)
        ws.update(cell_range, [[f"♻️ ПЕРЕНОС: {guest_name}"]])

        # Форматируем красным цветом (как отмена)
        ws.format(cell_range, {
            "backgroundColor": {
                "red": 1.0,
                "green": 0.8,
                "blue": 0.8
            },
            "textFormat": {
                "foregroundColor": {
                    "red": 0.8,
                    "green": 0.0,
                    "blue": 0.0
                },
                "fontSize": 11,
                "bold": True
            }
        })

        print(f"✅ Перенос записан красным в строку {rescheduled_row}")
        return True

    except Exception as e:
        print(f"❌ Ошибка записи переноса: {e}")
        import traceback
        traceback.print_exc()
        return False


# === OPEN DATE FUNCTIONS ===

def _normalize_ws_title_for_compare(title: str) -> str:
    # В Google Sheets иногда встречается кириллическая "С" вместо латинской "C" (выглядят одинаково).
    # Нормализуем для устойчивого сравнения.
    if not title:
        return ""
    return (
        title.strip()
        .lower()
        .replace("с", "c")  # кириллическая 'с' -> латинская 'c'
    )


def _find_certificate_worksheet(ss):
    """
    Возвращает worksheet для Certificate 2025, учитывая частые опечатки/варианты (латинская vs кириллическая C).
    """
    aliases = [
        "Certificate 2025",
        "Сertificate 2025",  # кириллическая C
        "Certificate2025",
        "Сertificate2025",
    ]

    # 1) Сначала пробуем точные варианты
    for name in aliases:
        ws = get_worksheet_by_title(ss, name)
        if ws:
            return ws

    # 2) Фолбек: сравнение по нормализованному названию среди всех листов
    try:
        wanted = {_normalize_ws_title_for_compare(a) for a in aliases}
        for ws in ss.worksheets():
            if _normalize_ws_title_for_compare(getattr(ws, "title", "")) in wanted:
                return ws
    except Exception:
        pass

    return None


async def write_open_date_to_certificate(pilgrim_data_list, booking_data):
    """
    Записывает паломников в таблицу Certificate для OPEN DATE.

    🔍 ЛОГИКА ПОИСКА:
    1. Ищет таблицу где в названии есть "сертификат", "certificate", "сертификаты"
    2. Ищет лист где в названии есть "Certificate 2025" или вариации
    3. В первых 10 строках ищет заголовки

    Args:
        pilgrim_data_list: Список паломников [{last_name, first_name, gender, dob, passport_num, passport_expiry, iin}, ...]
        booking_data: Общие данные брони {room_type, meal_type, price, region, departure_city, client_phone, manager_name_text, comment}

    Returns:
        list: Список номеров строк в Google Sheets, куда были записаны паломники
    """
    try:
        print(f"\n📝 Запись OPEN DATE в Certificate таблицу...")
        print(f"   Паломников: {len(pilgrim_data_list)}")

        # ШАГ 1: Получаем клиент Google Sheets
        client = get_google_client()
        if not client:
            print("❌ Не удалось получить Google клиент")
            return []

        # ШАГ 2: Ищем таблицу по ключевым словам
        print(f"\n🔍 Шаг 1: Поиск таблицы с сертификатами...")

        certificate_keywords = ["сертификат", "certificate", "сертификаты", "cert"]

        try:
            all_spreadsheets = client.openall()
            print(f"   Найдено таблиц всего: {len(all_spreadsheets)}")

            ss = None
            for spreadsheet in all_spreadsheets:
                title_lower = spreadsheet.title.lower()
                if any(keyword in title_lower for keyword in certificate_keywords):
                    ss = spreadsheet
                    print(f"   ✅ Найдена таблица: '{spreadsheet.title}'")
                    break

            if not ss:
                print(f"   ❌ Не найдена таблица с ключевыми словами: {certificate_keywords}")
                print(f"   📋 Доступные таблицы:")
                for s in all_spreadsheets[:10]:  # Показываем первые 10
                    print(f"      - {s.title}")
                return []

        except Exception as e:
            print(f"   ❌ Ошибка поиска таблицы: {e}")
            return []

        # ШАГ 3: Ищем лист "Certificate 2025" (с вариациями)
        print(f"\n🔍 Шаг 2: Поиск листа Certificate 2025...")

        def _norm_title(t: str) -> str:
            """Нормализует название: убирает пробелы, lower case, кириллическая 'с' -> латинская 'c'"""
            t = (t or "").strip().lower()
            t = t.replace("с", "c")  # кириллическая → латинская
            return t

        sheet_keywords = ["certificate 2025", "certificate2025", "cert 2025"]

        try:
            worksheets = ss.worksheets()
            print(f"   Найдено листов: {len(worksheets)}")

            ws = None
            for w in worksheets:
                norm_title = _norm_title(w.title)
                if any(keyword in norm_title for keyword in sheet_keywords):
                    ws = w
                    print(f"   ✅ Найден лист: '{w.title}'")
                    break

            if not ws:
                print(f"   ❌ Не найден лист с ключевыми словами: {sheet_keywords}")
                print(f"   📄 Доступные листы:")
                for w in worksheets[:10]:  # Показываем первые 10
                    print(f"      - {w.title}")
                return []

        except Exception as e:
            print(f"   ❌ Ошибка поиска листа: {e}")
            return []

        # ШАГ 4: Получаем данные листа
        print(f"\n🔍 Шаг 3: Поиск заголовков в первых 10 строках...")
        all_values = ws.get_all_values()

        if not all_values:
            print("❌ Таблица пуста")
            return []

        # Ищем строку с заголовками в первых 10 строках
        header_row_idx = None
        col_map = {}

        # Ключевые слова которые должны быть в заголовках
        header_keywords = ['фамилия', 'имя', 'male', 'female', 'иин', 'телефон']

        for row_idx in range(min(10, len(all_values))):
            row = all_values[row_idx]
            row_text = " ".join([str(cell).lower() for cell in row])

            # Проверяем есть ли хотя бы 2 ключевых слова в этой строке
            keyword_count = sum(1 for kw in header_keywords if kw in row_text)

            if keyword_count >= 2:
                # Похоже на строку с заголовками
                header_row_idx = row_idx
                headers = row
                print(f"   ✅ Заголовки найдены в строке {row_idx + 1}")
                print(f"   📋 Заголовки: {headers[:10]}...")  # Показываем первые 10

                # Создаем карту колонок
                for idx, header in enumerate(headers):
                    header_lower = header.strip().lower()
                    if 'фамилия' in header_lower and 'имя' in header_lower:
                        col_map['name'] = idx
                    elif 'male' in header_lower and 'female' in header_lower:
                        col_map['gender'] = idx
                    elif 'иин' in header_lower:
                        col_map['iin'] = idx
                    elif 'date of birth' in header_lower or 'дата рождения' in header_lower:
                        col_map['dob'] = idx
                    elif 'телефон' in header_lower:
                        col_map['phone'] = idx
                    elif 'размещение' in header_lower:
                        col_map['room'] = idx
                    elif 'питание' in header_lower:
                        col_map['meal'] = idx
                    elif 'к оплате' in header_lower or 'оплате' in header_lower:
                        col_map['price'] = idx
                    elif 'город' in header_lower:
                        col_map['city'] = idx
                    elif 'менеджер' in header_lower:
                        col_map['manager'] = idx
                    elif 'комментарий' in header_lower:
                        col_map['comment'] = idx
                break

        if header_row_idx is None:
            print(f"   ❌ Заголовки не найдены в первых 10 строках")
            print(f"   📋 Первые строки таблицы:")
            for i in range(min(5, len(all_values))):
                print(f"      Строка {i+1}: {all_values[i][:5]}")
            return []

        if not col_map:
            print(f"   ❌ Не удалось распознать колонки")
            return []

        print(f"   ✅ Карта колонок: {col_map}")

        # ШАГ 5: Находим последнюю заполненную строку (смотрим на колонку name)
        print(f"\n🔍 Шаг 4: Поиск последней заполненной строки...")

        # Начинаем искать ПОСЛЕ строки с заголовками
        last_row = header_row_idx + 1  # Строка после заголовков (в терминах Google Sheets, 1-indexed)
        name_col = col_map.get('name', 0)

        for row_idx in range(header_row_idx + 1, len(all_values)):
            row_data = all_values[row_idx]
            if row_data and len(row_data) > name_col:
                cell_value = str(row_data[name_col]).strip()
                # Проверяем не пустая ли ячейка
                if cell_value and cell_value != '':
                    last_row = row_idx + 1  # +1 потому что Google Sheets индексация с 1

        print(f"   ✅ Последняя заполненная строка: {last_row}")
        print(f"   📍 Новые паломники будут записаны начиная со строки: {last_row + 1}")

        # ШАГ 6: Записываем паломников
        print(f"\n🔍 Шаг 5: Запись {len(pilgrim_data_list)} паломников...")

        insert_row = last_row + 1
        saved_rows = []

        for idx, pilgrim in enumerate(pilgrim_data_list, 1):
            print(f"\n   [{idx}/{len(pilgrim_data_list)}] Записываем: {pilgrim.get('last_name', '')} {pilgrim.get('first_name', '')}")

            updates = []

            # Подготавливаем данные для записи
            full_name = f"{pilgrim.get('last_name', '')} {pilgrim.get('first_name', '')}"
            gender = pilgrim.get('gender', '')
            iin = pilgrim.get('iin', '')
            dob = pilgrim.get('date_of_birth', '')
            phone = booking_data.get('client_phone', '')
            room_type = booking_data.get('room_type', '')
            meal_type = booking_data.get('meal_type', '')
            price = booking_data.get('price', '')
            city = booking_data.get('departure_city', '')
            manager = booking_data.get('manager_name_text', '')
            comment = booking_data.get('comment', '')

            # Записываем данные в соответствующие колонки
            if 'name' in col_map:
                cell = row_col_to_a1(insert_row, col_map['name'] + 1)
                updates.append({'range': cell, 'values': [[full_name]]})

            if 'gender' in col_map:
                cell = row_col_to_a1(insert_row, col_map['gender'] + 1)
                updates.append({'range': cell, 'values': [[gender]]})

            if 'iin' in col_map:
                cell = row_col_to_a1(insert_row, col_map['iin'] + 1)
                updates.append({'range': cell, 'values': [[iin]]})

            if 'dob' in col_map:
                cell = row_col_to_a1(insert_row, col_map['dob'] + 1)
                updates.append({'range': cell, 'values': [[dob]]})

            if 'phone' in col_map:
                cell = row_col_to_a1(insert_row, col_map['phone'] + 1)
                updates.append({'range': cell, 'values': [[phone]]})

            if 'room' in col_map:
                cell = row_col_to_a1(insert_row, col_map['room'] + 1)
                updates.append({'range': cell, 'values': [[room_type]]})

            if 'meal' in col_map:
                cell = row_col_to_a1(insert_row, col_map['meal'] + 1)
                updates.append({'range': cell, 'values': [[meal_type]]})

            if 'price' in col_map:
                cell = row_col_to_a1(insert_row, col_map['price'] + 1)
                updates.append({'range': cell, 'values': [[price]]})

            if 'city' in col_map:
                cell = row_col_to_a1(insert_row, col_map['city'] + 1)
                updates.append({'range': cell, 'values': [[city]]})

            if 'manager' in col_map:
                cell = row_col_to_a1(insert_row, col_map['manager'] + 1)
                updates.append({'range': cell, 'values': [[manager]]})

            if 'comment' in col_map:
                cell = row_col_to_a1(insert_row, col_map['comment'] + 1)
                updates.append({'range': cell, 'values': [[comment]]})

            # Применяем обновления
            if updates:
                ws.batch_update(updates)
                print(f"   ✅ Паломник записан в строку {insert_row}")
                saved_rows.append(insert_row)
                insert_row += 1
            else:
                print(f"   ⚠️ Нет данных для записи паломника")

        print(f"\n{'='*60}")
        print(f"✅ УСПЕШНО: Записано {len(saved_rows)} паломников")
        print(f"   📊 Таблица: {ss.title}")
        print(f"   📄 Лист: {ws.title}")
        print(f"   📍 Строки: {saved_rows}")
        print(f"{'='*60}\n")
        return saved_rows

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ОШИБКА записи в Certificate таблицу")
        print(f"   {type(e).__name__}: {e}")
        print(f"{'='*60}\n")
        import traceback
        traceback.print_exc()
        return []


async def move_pilgrim_from_certificate_to_used(pilgrim_full_name, selected_date, new_booking_data):
    """
    Переносит паломника из Certificate 2025 в лист ИСПОЛЬЗОВАННЫЕ.

    Args:
        pilgrim_full_name: Полное имя паломника для поиска
        selected_date: Выбранная дата
        new_booking_data: Данные нового бронирования

    Returns:
        bool: True если успешно, False если ошибка
    """
    CERTIFICATE_TABLE_ID = "1IKLFtRq7tSTuU3dyVf8u0vhGswDBBh9rhj1R8B6WI8c"
    USED_SHEET_NAME = "ИСПОЛЬЗОВАННЫЕ"

    try:
        print(f"\n🔄 Перенос паломника {pilgrim_full_name} из Certificate в ИСПОЛЬЗОВАННЫЕ...")

        # Получаем клиент
        client = get_google_client()
        if not client:
            print("❌ Не удалось получить Google клиент")
            return False

        ss = client.open_by_key(CERTIFICATE_TABLE_ID)

        # Открываем Certificate лист (с вариациями названия)
        ws_cert = _find_certificate_worksheet(ss)
        if not ws_cert:
            print("❌ Лист 'Certificate 2025' не найден (включая вариации названия)")
            return False

        # Ищем паломника в Certificate 2025
        all_values = ws_cert.get_all_values()
        headers_cert = all_values[0]

        # Находим колонку с именем
        name_col = None
        for idx, header in enumerate(headers_cert):
            if 'фамилия' in header.lower() and 'имя' in header.lower():
                name_col = idx
                break

        if name_col is None:
            print("❌ Не найдена колонка с именем в Certificate 2025")
            return False

        # Ищем строку с паломником
        pilgrim_row = None
        pilgrim_data = None
        for row_idx in range(1, len(all_values)):
            row = all_values[row_idx]
            if row and len(row) > name_col:
                cell_value = str(row[name_col]).strip()
                if cell_value.lower() == pilgrim_full_name.lower():
                    pilgrim_row = row_idx + 1  # +1 для Google Sheets индексации
                    pilgrim_data = row
                    break

        if not pilgrim_row:
            print(f"❌ Паломник {pilgrim_full_name} не найден в Certificate 2025")
            return False

        print(f"   Найден паломник в строке {pilgrim_row}")

        # Удаляем строку из Certificate 2025
        ws_cert.delete_rows(pilgrim_row)
        print(f"   ✅ Строка удалена из Certificate 2025")

        # Записываем в лист ИСПОЛЬЗОВАННЫЕ
        ws_used = get_worksheet_by_title(ss, USED_SHEET_NAME)
        if not ws_used:
            print(f"❌ Лист '{USED_SHEET_NAME}' не найден")
            return False

        # Получаем заголовки ИСПОЛЬЗОВАННЫЕ
        all_values_used = ws_used.get_all_values()
        headers_used = all_values_used[0] if all_values_used else []

        # Находим последнюю заполненную строку
        last_used_row = len(all_values_used) + 1

        # Создаем карту колонок для ИСПОЛЬЗОВАННЫЕ
        used_col_map = {}
        for idx, header in enumerate(headers_used):
            header_lower = header.strip().lower()
            if 'фамилия' in header_lower and 'имя' in header_lower:
                used_col_map['name'] = idx
            elif 'выбранная дата' in header_lower:
                used_col_map['selected_date'] = idx
            elif 'пакет' in header_lower:
                used_col_map['package'] = idx
            # Добавьте другие колонки по необходимости

        # Записываем данные
        updates = []

        if 'name' in used_col_map:
            cell = row_col_to_a1(last_used_row, used_col_map['name'] + 1)
            updates.append({'range': cell, 'values': [[pilgrim_full_name]]})

        if 'selected_date' in used_col_map:
            cell = row_col_to_a1(last_used_row, used_col_map['selected_date'] + 1)
            updates.append({'range': cell, 'values': [[selected_date]]})

        if 'package' in used_col_map and new_booking_data.get('package_name'):
            cell = row_col_to_a1(last_used_row, used_col_map['package'] + 1)
            updates.append({'range': cell, 'values': [[new_booking_data.get('package_name')]]})

        # Применяем обновления
        if updates:
            ws_used.batch_update(updates)
            print(f"   ✅ Паломник записан в ИСПОЛЬЗОВАННЫЕ (строка {last_used_row})")

        print(f"✅ Паломник успешно перенесен")
        return True

    except Exception as e:
        print(f"❌ Ошибка переноса паломника: {e}")
        import traceback
        traceback.print_exc()
        return False
