from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from backend import (
    init_db,
    check_nickname, check_password,
    create_user, verify_user, get_user_by_id,
    create_group, join_group, get_user_groups,
    add_expense, delete_expense, get_expenses,
    get_group_stats, get_personal_total, get_categories,
    add_debt, delete_debt, get_group_debts, get_group_members_for_select,
    add_notification, get_notifications, get_unread_count,
    mark_notification_read, mark_all_notifications_read
)
from ai_service import ask_ai, categorize_expense, analyze_group_expenses, generate_debt_reminder

app = Flask(__name__)
app.secret_key = "change-this-to-random-secret-key"
DEFAULT_CATEGORIES = ["Еда", "Транспорт", "Развлечения", "Жильё", "Здоровье", "Другое"]


def get_current_user():
    user_id = session.get("user_id")
    real_name = session.get("real_name")
    if user_id and real_name:
        return {"id": user_id, "real_name": real_name}
    return None


# ==================== СТРАНИЦЫ ====================

@app.route("/")
def index():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    groups = get_user_groups(user["id"])
    current_group_id = request.args.get("group", "personal")
    current_month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    category_filter = request.args.get("category", "")
    today = datetime.now().strftime("%Y-%m-%d")

    current_group_code = ""
    if current_group_id == "personal":
        expenses = get_expenses(month=current_month, category=category_filter or None, user_id=user["id"])
        total = get_personal_total(user["id"], current_month)
        group_stats = None
        current_group_name = "Личные расходы"
    else:
        group_id = int(current_group_id)
        expenses = get_expenses(month=current_month, category=category_filter or None, group_id=group_id)
        group_stats = get_group_stats(group_id, current_month)
        total = group_stats["total"]
        group_info = next((g for g in groups if g["id"] == group_id), None)
        current_group_name = group_info["name"] if group_info else "Группа"
        current_group_code = group_info["code"] if group_info else ""

    categories = sorted(set(DEFAULT_CATEGORIES + get_categories()))

    return render_template(
        "index.html",
        user=user,
        groups=groups,
        current_group_id=current_group_id,
        current_group_name=current_group_name,
        current_group_code=current_group_code,
        expenses=expenses,
        total=total,
        group_stats=group_stats,
        current_month=current_month,
        category_filter=category_filter,
        categories=categories,
        default_categories=DEFAULT_CATEGORIES,
        today=today
    )


# ==================== АВТОРИЗАЦИЯ ====================

@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("index"))

    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        password = request.form.get("password", "")

        user = verify_user(nickname, password)
        if user:
            session["user_id"] = user["id"]
            session["real_name"] = user["real_name"]
            return redirect(url_for("index"))
        else:
            flash("Неверный никнейм или пароль", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("index"))

    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        real_name = request.form.get("real_name", "").strip()
        password = request.form.get("password", "")

        err = check_nickname(nickname)
        if err:
            flash(err, "error")
            return render_template("register.html", nickname=nickname, real_name=real_name)

        err = check_password(password)
        if err:
            flash(err, "error")
            return render_template("register.html", nickname=nickname, real_name=real_name)

        try:
            user_id = create_user(nickname, real_name, password)
            session["user_id"] = user_id
            session["real_name"] = real_name
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("Такой никнейм уже занят!", "error")
            return render_template("register.html", nickname=nickname, real_name=real_name)

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================== ГРУППЫ ====================

@app.route("/create-group", methods=["POST"])
def create_group_route():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    group_name = request.form.get("group_name", "").strip()
    if not group_name:
        return redirect(url_for("index"))

    # Проверяем, не существует ли уже группа с таким названием у этого пользователя
    existing_groups = get_user_groups(user["id"])
    for g in existing_groups:
        if g["name"].lower() == group_name.lower():
            flash("Группа с таким названием уже существует", "error")
            return redirect(url_for("index"))

    group = create_group(group_name)
    join_group(group["code"], user["id"])
    return redirect(url_for("index", group=group["id"]))


@app.route("/join-group", methods=["POST"])
def join_group_route():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    code = request.form.get("code", "").strip().upper()
    if not code:
        return redirect(url_for("index"))

    group = join_group(code, user["id"])
    if group:
        return redirect(url_for("index", group=group["id"]))
    else:
        flash("Группа не найдена", "error")
        return redirect(url_for("index"))


# ==================== РАСХОДЫ ====================

@app.route("/add", methods=["POST"])
def add():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    try:
        amount = float(request.form["amount"].replace(",", "."))
    except ValueError:
        return redirect(url_for("index"))

    category = request.form.get("category", "").strip()
    custom_category = request.form.get("custom_category", "").strip()
    if category == "__custom__" and custom_category:
        category = custom_category
    if not category:
        category = "Другое"

    description = request.form.get("description", "").strip()
    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    group_id_param = request.form.get("group_id", "personal")
    group_id = None if group_id_param == "personal" else int(group_id_param)

    add_expense(amount, category, description, date, user["id"], group_id)
    return redirect(url_for("index", group=group_id_param))


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    delete_expense(expense_id)
    group_id = request.form.get("group_id", "personal")
    return redirect(url_for("index", group=group_id))


# ============ AI-CHAT С КОНТЕКСТОМ ============
@app.route("/api/ai/ask", methods=["POST"])
def api_ask():
    try:
        import sqlite3
        db = sqlite3.connect('expenses.db')
        db.row_factory = sqlite3.Row
        
        data = request.get_json()
        question = data.get("question", "").strip()
        group_id = data.get("group_id", "personal")
        
        if not question:
            return jsonify({
                "success": False,
                "error": "Вопрос не может быть пустым"
            }), 400
        
        # Получаем текущего пользователя
        user = session.get("user", {})
        user_name = user.get("real_name", "Пользователь")
        
        # Собираем контекст: долги, участники, расходы
        debts = []
        members = []
        expenses = []
        
        if group_id and group_id != "personal":
            # Активные долги группы
            debts = db.execute("""
                SELECT d.*, u1.real_name as debtor_name, u2.real_name as creditor_name
                FROM debts d
                JOIN users u1 ON d.debtor_id = u1.id
                JOIN users u2 ON d.creditor_id = u2.id
                WHERE d.group_id = ?
            """, (group_id,)).fetchall()
            debts = [dict(d) for d in debts]
            
            # Участники группы
            members = db.execute("""
                SELECT u.real_name
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
            """, (group_id,)).fetchall()
            members = [dict(m) for m in members]
            
            # Последние 10 расходов
            expenses = db.execute("""
                SELECT e.*, u.real_name as user_name
                FROM expenses e
                JOIN users u ON e.user_id = u.id
                WHERE e.group_id = ?
                ORDER BY e.date DESC
                LIMIT 10
            """, (group_id,)).fetchall()
            expenses = [dict(e) for e in expenses]
        
        # Формируем промпт с контекстом
        prompt = f"""Ты — AI-ассистент приложения для учёта расходов "Новые Лица".

ИНФОРМАЦИЯ О ПРИЛОЖЕНИИ:
- Приложение для совместного учёта расходов и долгов
- Пользователи создают группы и добавляют общие расходы
- Система автоматически считает, кто кому должен
- Есть AI-аналитика, автокатегоризация и чат-ассистент
- Основные разделы: Главная (расходы, долги, AI-чат), Аналитика (AI-анализ расходов)

КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:
- Имя: {user_name}
- Текущая группа: {'Личные расходы' if group_id == 'personal' else 'Группа #' + str(group_id)}
"""
        
        if debts:
            prompt += "\nАКТИВНЫЕ ДОЛГИ В ГРУППЕ:\n"
            for debt in debts:
                prompt += f"- {debt['debtor_name']} должен {debt['creditor_name']} {debt['amount']}₽"
                if debt.get('description'):
                    prompt += f" ({debt['description']})"
                prompt += "\n"
        else:
            prompt += "\nАктивных долгов в группе нет.\n"
        
        if members:
            prompt += "\nУЧАСТНИКИ ГРУППЫ:\n"
            for m in members:
                prompt += f"- {m['real_name']}\n"
        
        if expenses:
            prompt += "\nПОСЛЕДНИЕ РАСХОДЫ (до 10):\n"
            for exp in expenses:
                prompt += f"- {exp.get('date', '')}: {exp.get('user_name', '')} — {exp.get('amount', 0)}₽ на {exp.get('category', '')}"
                if exp.get('description'):
                    prompt += f" ({exp['description']})"
                prompt += "\n"
        
        prompt += f"""
ВОПРОС ПОЛЬЗОВАТЕЛЯ: "{question}"

ПРАВИЛА ОТВЕТА:
"Форматируй ответ в Markdown:"
"- Используй **жирный** для важного"
"- Используй нумерованные списки (1. 2. 3.)"
"- Используй маркированные списки (- пункт)"
"- Делай переносы строк между пунктами"
"- Используй ### для заголовков"
- Отвечай кратко, дружелюбно и по делу
- Если вопрос про долги — используй данные из "АКТИВНЫЕ ДОЛГИ"
- Если вопрос про расходы — используй данные из "ПОСЛЕДНИЕ РАСХОДЫ"
- Если вопрос про навигацию по сайту — объясни, где найти нужную функцию
- Если не знаешь ответа — предложи задать вопрос про долги, расходы или аналитику
- Отвечай на русском языке

Ответ:"""
        
        answer = ask_ai(prompt)
        
        return jsonify({
            "success": True,
            "answer": answer
        })
        
    except Exception as e:
        print(f"Ошибка AI-ассистента: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@app.route("/api/ai/categorize", methods=["POST"])
def api_categorize():
    """AI-категоризация расхода"""
    try:
        data = request.get_json()
        description = data.get("description", "")
        
        if not description:
            return jsonify({"category": "Другое"})
        
        from ai_service import categorize_expense
        category = categorize_expense(description)
        
        print(f"=== КАТЕГОРИЗАЦИЯ ===")
        print(f"Описание: {description}")
        print(f"Категория: {category}")
        print(f"====================")
        
        return jsonify({"category": category})
        
    except Exception as e:
        print(f"Ошибка категоризации: {e}")
        return jsonify({"category": "Другое", "error": str(e)})


# ==================== AI-АНАЛИТИКА ====================

@app.route("/ai-analytics")
def ai_analytics():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    groups = get_user_groups(user["id"])
    return render_template("ai_analytics.html", user=user, groups=groups)


@app.route("/api/ai/analyze", methods=["POST"])
def api_analyze():
    try:
        data = request.get_json()
        expenses = data.get("expenses", [])

        if not expenses:
            return jsonify({"error": "Нет данных"}), 400

        result = analyze_group_expenses(expenses)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/expenses")
def api_expenses():
    user = get_current_user()
    if not user:
        return jsonify([])

    group_id = request.args.get("group", "personal")
    current_month = datetime.now().strftime("%Y-%m")

    if group_id == "personal":
        expenses = get_expenses(month=current_month, user_id=user["id"])
    else:
        expenses = get_expenses(month=current_month, group_id=int(group_id))

    result = []
    for e in expenses:
        row_dict = dict(e)
        result.append({
            "id": row_dict.get("id"),
            "user_name": row_dict.get("user_name") or user["real_name"],
            "category": row_dict.get("category", ""),
            "amount": float(row_dict.get("amount", 0)),
            "description": row_dict.get("description", ""),
            "date": str(row_dict.get("date", ""))
        })
    return jsonify(result)


# ==================== ДОЛГИ ====================

@app.route("/api/debts")
def api_debts():
    user = get_current_user()
    if not user:
        return jsonify([])

    current_group_id = request.args.get("group", "personal")
    if current_group_id == "personal":
        return jsonify([])

    try:
        group_id = int(current_group_id)
        debts_raw = get_group_debts(group_id)
        debts = []
        for d in debts_raw:
            debts.append({
                "id": d["id"],
                "debtor_id": d["debtor_id"],
                "creditor_id": d["creditor_id"],
                "debtor_name": d["debtor_name"],
                "creditor_name": d["creditor_name"],
                "amount": float(d["amount"]),
                "description": d["description"] or ""
            })
        return jsonify(debts)
    except Exception as e:
        print(f"Ошибка получения долгов: {e}")
        return jsonify([])


@app.route("/api/add-debt", methods=["POST"])
def api_add_debt():
    try:
        data = request.get_json()
        group_id = data.get("group_id")
        debtor_id = data.get("debtor_id")
        creditor_id = data.get("creditor_id")
        amount = float(data.get("amount", 0))
        description = data.get("description", "")

        if not all([group_id, debtor_id, creditor_id]):
            return jsonify({"error": "Не все обязательные поля заполнены"}), 400

        if debtor_id == creditor_id:
            return jsonify({"error": "Должник и кредитор не могут быть одним лицом"}), 400

        debtor = get_user_by_id(debtor_id)
        creditor = get_user_by_id(creditor_id)
        if not debtor or not creditor:
            return jsonify({"error": "Пользователь не найден"}), 404

        add_debt(group_id, debtor_id, creditor_id, amount, description)

        return jsonify({
            "success": True,
            "message": "Долг добавлен"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/delete-debt/<int:debt_id>", methods=["POST"])
def api_delete_debt(debt_id):
    try:
        delete_debt(debt_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/group-members/<int:group_id>")
def api_group_members(group_id):
    try:
        members = get_group_members_for_select(group_id)
        return jsonify([{"id": m["id"], "real_name": m["real_name"]} for m in members])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/remind", methods=["POST"])
def api_remind():
    try:
        data = request.get_json()
        debtor_id = data.get("debtor_id")
        creditor_id = data.get("creditor_id")
        amount = float(data.get("amount", 0))
        description = data.get("description", "")

        if not debtor_id or not creditor_id:
            return jsonify({"error": "Не указан должник или кредитор"}), 400

        debtor = get_user_by_id(debtor_id)
        creditor = get_user_by_id(creditor_id)
        if not debtor or not creditor:
            return jsonify({"error": "Пользователь не найден"}), 404

        reminder_text = generate_debt_reminder(
            debtor_name=debtor["real_name"],
            creditor_name=creditor["real_name"],
            amount=amount,
            description=description or "общие расходы"
        )

        notification_id = add_notification(
            user_id=debtor_id,
            from_user_id=creditor_id,
            message=reminder_text,
            amount=amount,
            description=description
        )

        return jsonify({
            "success": True,
            "notification_id": notification_id,
            "message": reminder_text
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== УВЕДОМЛЕНИЯ ====================

@app.route("/api/notifications")
def api_notifications():
    user = get_current_user()
    if not user:
        return jsonify([])

    notifications = get_notifications(user["id"])
    return jsonify(notifications)


@app.route("/api/notifications/unread-count")
def api_unread_count():
    user = get_current_user()
    if not user:
        return jsonify({"count": 0})

    count = get_unread_count(user["id"])
    return jsonify({"count": count})


@app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def api_mark_read(notification_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    mark_notification_read(notification_id, user["id"])
    return jsonify({"success": True})


@app.route("/api/notifications/read-all", methods=["POST"])
def api_mark_all_read():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    mark_all_notifications_read(user["id"])
    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)