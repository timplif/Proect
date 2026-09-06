import sys
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_connection
from backend.queries_db import (
    create_user,
    create_group,
    join_group,
    add_expense,
    add_debt,
)
from backend.init_db import init_db   # 👈 импортируем инициализацию

def seed():
    # 1. Создаём таблицы, если их ещё нет
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    # Отключаем проверку внешних ключей для очистки
    cursor.execute("PRAGMA foreign_keys = OFF;")

    # Очищаем таблицы в правильном порядке (дочерние → родительские)
    cursor.execute("DELETE FROM debts;")
    cursor.execute("DELETE FROM expenses;")
    cursor.execute("DELETE FROM group_members;")
    cursor.execute("DELETE FROM groups;")
    cursor.execute("DELETE FROM users;")

    # Сбрасываем автоинкремент (для SQLite)
    cursor.execute("DELETE FROM sqlite_sequence;")

    # Включаем проверку обратно
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()

    print("🧹 База данных очищена")

    # --- 1. Создание пользователей ---
    # Пароли должны соответствовать требованиям: минимум 8 символов, заглавная, цифра, спецсимвол
    users_data = [
        {"nickname": "lesha", "real_name": "Лёша", "password": "Password123!"},
        {"nickname": "masha", "real_name": "Маша", "password": "Password123!"},
        {"nickname": "katya", "real_name": "Катя", "password": "Password123!"},
        {"nickname": "anya", "real_name": "Аня", "password": "Password123!"},
    ]

    users = []
    for u in users_data:
        user_id = create_user(u["nickname"], u["real_name"], u["password"])
        # Получаем созданного пользователя (можно через get_user_by_id, но в seed мы можем сохранить id)
        users.append({"id": user_id, "nickname": u["nickname"], "real_name": u["real_name"]})
    print(f"✅ Создано пользователей: {len(users)}")

    # --- 2. Создание группы ---
    group = create_group("Квартира")
    group_id = group["id"]
    group_code = group["code"]
    print(f"✅ Группа '{group['name']}' (код: {group_code})")

    # --- 3. Добавление участников в группу ---
    for user in users:
        join_group(group_code, user["id"])
    print("✅ Все пользователи добавлены в группу")

    # --- 4. Добавление расходов (expenses) ---
    # Данные для расходов: список словарей с обязательными полями
    expenses_data = [
        # Сентябрь 2026 (групповые расходы)
        {"user": "lesha", "amount": 5200, "category": "Продукты", "description": "Пятёрочка", "date": "2026-09-01"},
        {"user": "masha", "amount": 1800, "category": "Транспорт", "description": "Метро", "date": "2026-09-02"},
        {"user": "katya", "amount": 2500, "category": "Развлечения", "description": "Кино", "date": "2026-09-03"},
        {"user": "anya", "amount": 4800, "category": "Продукты", "description": "Магнит", "date": "2026-09-04"},
        {"user": "lesha", "amount": 8000, "category": "Жильё", "description": "Квартплата", "date": "2026-09-05"},
        {"user": "masha", "amount": 1500, "category": "Здоровье", "description": "Аптека", "date": "2026-09-06"},
        {"user": "katya", "amount": 3200, "category": "Развлечения", "description": "Суши Wok", "date": "2026-09-07"},
        {"user": "anya", "amount": 900, "category": "Транспорт", "description": "Яндекс Go", "date": "2026-09-08"},
        # Август 2026
        {"user": "lesha", "amount": 6100, "category": "Продукты", "description": "Ашан", "date": "2026-08-05"},
        {"user": "masha", "amount": 4500, "category": "Развлечения", "description": "Netflix", "date": "2026-08-10"},
        {"user": "katya", "amount": 5500, "category": "Продукты", "description": "ВкусВилл", "date": "2026-08-15"},
        {"user": "anya", "amount": 8000, "category": "Жильё", "description": "Электричество", "date": "2026-08-20"},
        # Июль 2026
        {"user": "lesha", "amount": 2800, "category": "Развлечения", "description": "KFC", "date": "2026-07-05"},
        {"user": "masha", "amount": 5900, "category": "Продукты", "description": "Пятёрочка", "date": "2026-07-10"},
        {"user": "katya", "amount": 2200, "category": "Транспорт", "description": "UBER", "date": "2026-07-15"},
        {"user": "anya", "amount": 3500, "category": "Здоровье", "description": "Фитнес", "date": "2026-07-20"},
    ]

    user_map = {u["nickname"]: u["id"] for u in users}
    expense_count = 0
    for e in expenses_data:
        user_id = user_map.get(e["user"])
        if not user_id:
            print(f"⚠️ Пользователь {e['user']} не найден, пропускаем")
            continue

        # Если personal == True, group_id = None, иначе group_id
        group_id_for_expense = None if e.get("personal") else group_id

        # Добавляем расход через функцию
        add_expense(
            amount=e["amount"],
            category=e["category"],
            description=e["description"],
            date=e["date"],
            user_id=user_id,
            group_id=group_id_for_expense,
        )
        expense_count += 1

    print(f"✅ Добавлено расходов: {expense_count}")

    # --- 5. Добавление долгов (debts) ---
    # Создаём долги между участниками группы
    debts_data = [
    {"debtor": "masha", "creditor": "lesha", "amount": 2900, "description": "Расчёт долгов группы"},
    {"debtor": "katya", "creditor": "lesha", "amount": 2600, "description": "Расчёт долгов группы"},
    {"debtor": "katya", "creditor": "anya", "amount": 600, "description": "Расчёт долгов группы"},
]

    debt_count = 0
    for d in debts_data:
        debtor_id = user_map.get(d["debtor"])
        creditor_id = user_map.get(d["creditor"])
        if not debtor_id or not creditor_id:
            print(f"⚠️ Не найден должник или кредитор для {d['debtor']} -> {d['creditor']}, пропускаем")
            continue
        add_debt(
            group_id=group_id,
            debtor_id=debtor_id,
            creditor_id=creditor_id,
            amount=d["amount"],
            description=d["description"],
        )
        debt_count += 1

    print(f"✅ Добавлено долгов: {debt_count}")

    print("🎉 Seed успешно выполнен!")

if __name__ == "__main__":
    seed()