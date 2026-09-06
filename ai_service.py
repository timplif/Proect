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
    """Анализ расходов группы с повторными попытками"""
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
}}

ВАЖНО: отвечай ТОЛЬКО JSON без markdown и пояснений!"""
    
    # Повторные попытки (до 3 раз)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            import json
            import time
            
            content = ask_ai(prompt).strip()
            # Очистка markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            print(f"=== ПОПЫТКА {attempt + 1} ===")
            print(f"Ответ AI: {content[:200]}...")
            
            result = json.loads(content)
            
            # Проверка, что есть нужные поля
            if "advice" in result and isinstance(result["advice"], list):
                return {
                    "total": result.get("total", total),
                    "per_person": result.get("per_person", per_person),
                    "top_categories": result.get("top_categories", []),
                    "advice": result["advice"],
                    "potential_savings": result.get("potential_savings", 0)
                }
        except Exception as e:
            print(f"Ошибка попытки {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Ждём 2 секунды перед следующей попыткой
                continue
    
    # Если все попытки провалились — возвращаем базовый анализ
    print("Все попытки AI не удались, возвращаем базовый анализ")
    return {
        "total": total,
        "per_person": per_person,
        "advice": [
            f"Общие расходы: {total}₽",
            f"На человека: {per_person:.0f}₽",
            "Добавьте больше расходов для детальной аналитики"
        ],
        "top_categories": [],
        "potential_savings": 0
    }

def generate_debt_reminder(debtor_name: str, creditor_name: str, amount: float, description: str) -> str:
    """Генерация вежливого напоминания о долге"""
    prompt = f"""Напиши короткое вежливое напоминание от имени {creditor_name} для {debtor_name} о долге {amount}₽ за {description}.

Требования:
- Дружелюбный тон, можно с эмодзи
- 1-2 предложения
- Без агрессии
- На русском языке

Пример: "Лёша, привет! Напоминаю, что ты должен мне 1240₽ за продукты. Можешь перевести, когда удобно? 😊"

Напоминание:"""
    
    try:
        reminder = ask_ai(prompt).strip()
        return reminder
    except:
        return f"{debtor_name}, привет! Напоминаю о долге {amount}₽ за {description}."