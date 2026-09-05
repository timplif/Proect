import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def ask_ai(question: str) -> str:
    """AI-ассистент для ответов на вопросы"""
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "dots-studio/dots-3-note-preview:free",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты финансовый ассистент приложения учёта расходов. Отвечай кратко, понятно и дружелюбно."
                    },
                    {"role": "user", "content": question}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"Ошибка API: {response.status_code}"
    except Exception as e:
        return f"Ошибка: {str(e)}"


def categorize_expense(description: str) -> str:
    """Автокатегоризация расхода"""
    prompt = f"""Категория для: {description}
Варианты: Еда, Транспорт, Развлечения, Жильё, Здоровье, Другое
Напиши ТОЛЬКО одно слово из списка.
Ответ:"""
    try:
        category = ask_ai(prompt).strip()
        # Очистка
        category = category.replace("**", "").strip()
        for prefix in ["Ответ:", "Answer:", "Категория:"]:
            if category.startswith(prefix):
                category = category[len(prefix):].strip()
                break
        valid = ["Еда", "Транспорт", "Развлечения", "Жильё", "Здоровье", "Другое"]
        if category not in valid:
            for v in valid:
                if v.lower() in category.lower():
                    category = v
                    break
            else:
                category = "Другое"
        return category
    except:
        return "Другое"


def analyze_group_expenses(expenses: list) -> dict:
    """Анализ расходов группы"""
    if not expenses:
        return {"error": "Нет данных для анализа"}

    expenses_text = "\n".join([
        f"- {e.get('user_name', 'Неизвестно')}: {e['category']} - {e['amount']}₽ ({e.get('description', '')})"
        for e in expenses
    ])

    total = sum(e['amount'] for e in expenses)
    people = list(set(e.get('user_name', 'Неизвестно') for e in expenses))
    per_person = total / len(people) if people else 0

    prompt = f"""Проанализируй расходы группы сожителей:
{expenses_text}

Общая сумма: {total}₽
Участников: {len(people)}
Средний расход на человека: {per_person:.0f}₽

Дай краткий анализ в формате JSON:
{{
  "total": {total},
  "per_person": {per_person:.0f},
  "top_categories": [{{"category": "название", "total": сумма}}],
  "advice": ["совет1", "совет2", "совет3"],
  "potential_savings": сколько можно сэкономить в рублях
}}"""

    try:
        import json
        content = ask_ai(prompt).strip()
        # Очистка markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content)
    except Exception as e:
        return {
            "total": total,
            "per_person": per_person,
            "advice": ["Не удалось сгенерировать анализ"],
            "error": str(e)
        }


def generate_debt_reminder(debtor_name: str, creditor_name: str, amount: float, description: str) -> str:
    """Генерация вежливого напоминания о долге"""
    prompt = f"""Напиши короткое вежливое напоминание от имени {creditor_name} для {debtor_name} о долге {amount}₽ за {description}.

Требования:
- Дружелюбный тон, можно с эмодзи
- 1-2 предложения
- Без агрессии
- На русском языке

Пример: "Лёша, привет! 👋 Напоминаю, что ты должен мне 1240₽ за продукты. Можешь перевести, когда удобно? 😊"

Напоминание:"""

    try:
        reminder = ask_ai(prompt).strip()
        return reminder
    except:
        return f"{debtor_name}, привет! Напоминаю о долге {amount}₽ за {description}."