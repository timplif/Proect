from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import (
    init_db, check_nickname, check_password,
    create_user, verify_user, get_user_by_id,
    create_group, join_group, get_user_groups,
    add_expense, delete_expense, get_expenses,
    get_group_stats, get_personal_total, get_categories,
    init_debts_table, get_group_debts
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
# ==================== AI-ЧАТ ====================

@app.route("/chat")
def chat():
    """Страница чата с AI-ассистентом"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("chat.html", user=user)

@app.route("/api/ai/ask", methods=["POST"])
def api_ask():
    """API для вопросов к AI"""
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        
        if not question:
            return jsonify({
                "success": False,
                "error": "Вопрос не может быть пустым"
            }), 400
        
        answer = ask_ai(question)
        
        return jsonify({
            "success": True,
            "answer": answer
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/ai/categorize", methods=["POST"])
def api_categorize():
    """Автокатегоризация расхода"""
    try:
        data = request.get_json()
        description = data.get("description", "").strip()
        
        if not description:
            return jsonify({"success": False, "error": "Описание пустое"}), 400
        
        from ai_service import categorize_expense
        category = categorize_expense(description)
        
        return jsonify({"success": True, "category": category})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== AI-АНАЛИТИКА ====================

@app.route("/ai-analytics")
def ai_analytics():
    """Страница AI-аналитики"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("ai_analytics.html", user=user)

@app.route("/api/ai/analyze", methods=["POST"])
def api_analyze():
    """Анализ расходов группы"""
    try:
        data = request.get_json()
        expenses = data.get("expenses", [])
        
        if not expenses:
            return jsonify({"error": "Нет данных"}), 400
        
        from ai_service import analyze_group_expenses
        result = analyze_group_expenses(expenses)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/expenses")
def api_expenses():
    """Получить расходы для AI-анализа"""
    user = get_current_user()
    if not user:
        return jsonify([])
    
    group_id = request.args.get("group", "personal")
    current_month = datetime.now().strftime("%Y-%m")
    
    if group_id == "personal":
        expenses = get_expenses(month=current_month, category=None, user_id=user["id"])
    else:
        expenses = get_expenses(month=current_month, category=None, group_id=int(group_id))
    
    # Преобразуем в словари (безопасно)
    result = []
    for e in expenses:
        try:
            # Пытаемся получить как словарь
            if isinstance(e, dict):
                amount = float(e.get("amount", 0))
                result.append({
                    "user_name": e.get("user_name", user["real_name"]),
                    "category": e.get("category", ""),
                    "amount": amount,
                    "description": e.get("description", ""),
                    "date": str(e.get("date", ""))
                })
            else:
                # Если кортеж — берём по позициям с проверкой
                # Обычно: (id, date, user_name, category, amount, description)
                # Но порядок может отличаться, поэтому используем try
                amount = 0
                for val in e:
                    try:
                        amount = float(val)
                        break
                    except (ValueError, TypeError):
                        continue
                
                result.append({
                    "user_name": str(e[2]) if len(e) > 2 else user["real_name"],
                    "category": str(e[3]) if len(e) > 3 else "",
                    "amount": amount,
                    "description": str(e[5]) if len(e) > 5 else "",
                    "date": str(e[1]) if len(e) > 1 else ""
                })
        except Exception as ex:
            # Пропускаем битые записи
            print(f"Пропущена запись: {e}, ошибка: {ex}")
            continue
    
    return jsonify(result)

# ==================== AI-НАПОМИНАНИЯ О ДОЛГАХ ====================

@app.route("/reminders")
def reminders():
    """Страница напоминаний о долгах"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    
    init_debts_table()
    
    groups = get_user_groups(user["id"])
    current_group_id = request.args.get("group", "personal")
    
    return render_template(
        "reminders.html",
        user=user,
        groups=groups,
        current_group_id=current_group_id
    )

@app.route("/api/ai/reminders", methods=["POST"])
def api_reminders():
    """Генерация напоминаний о долгах"""
    try:
        data = request.get_json()
        debts = data.get("debts", [])
        
        if not debts:
            return jsonify({"reminders": []})
        
        reminders = []
        for debt in debts:
            reminder_text = generate_debt_reminder(
                debtor_name=debt.get("debtor_name", ""),
                creditor_name=debt.get("creditor_name", ""),
                amount=float(debt.get("amount", 0)),
                description=debt.get("description") or "общие расходы"
            )
            reminders.append({
                "debtor_name": debt.get("debtor_name"),
                "creditor_name": debt.get("creditor_name"),
                "amount": debt.get("amount"),
                "description": debt.get("description") or "",
                "reminder": reminder_text
            })
        
        return jsonify({"reminders": reminders})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/debts")
def api_debts():
    """Получить список долгов"""
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
                "debtor_name": d["debtor_name"],
                "creditor_name": d["creditor_name"],
                "amount": float(d["amount"]),
                "description": d["description"] or ""
            })
        
        return jsonify(debts)
    except Exception as e:
        print(f"Ошибка получения долгов: {e}")
        return jsonify([])


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

