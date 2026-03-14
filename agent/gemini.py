"""
Модуль работы с Gemini API.
Анализирует объявления с Krisha.kz и принимает решение — стоит ли писать продавцу.
"""

import json
import re
from dataclasses import dataclass

import google.generativeai as genai

from database.db import get_setting


@dataclass
class ListingAnalysis:
    score: int          # оценка 1–10
    approved: bool      # стоит ли писать продавцу
    comment: str        # краткий комментарий агента
    message: str        # готовое сообщение продавцу (если approved)


DEFAULT_MODEL = "gemini-2.5-flash-lite"


async def _get_model() -> genai.GenerativeModel:
    """Инициализирует Gemini с токеном и моделью из БД."""
    token = await get_setting("gemini_token")
    if not token:
        raise RuntimeError("Gemini API токен не настроен")
    model_name = await get_setting("gemini_model") or DEFAULT_MODEL
    genai.configure(api_key=token)
    return genai.GenerativeModel(model_name)


async def analyze_listing(listing: dict, client: dict) -> ListingAnalysis:
    """
    Анализирует одно объявление с точки зрения клиента.
    Возвращает оценку, решение и готовое сообщение продавцу.
    """
    model = await _get_model()

    # Формируем описание клиента для промпта
    client_desc = _format_client(client)
    listing_desc = _format_listing(listing)

    prompt = f"""Ты — ИИ-помощник риелтора. Проанализируй объявление о продаже/аренде недвижимости.

ПАРАМЕТРЫ КЛИЕНТА:
{client_desc}

ОБЪЯВЛЕНИЕ:
{listing_desc}

Оцени объявление и верни JSON в следующем формате (без markdown, только JSON):
{{
  "score": <число от 1 до 10, насколько объявление подходит клиенту>,
  "approved": <true если score >= 6 и объявление стоит рассмотреть, иначе false>,
  "comment": "<1-2 предложения: почему подходит или не подходит>",
  "message": "<если approved=true: сообщение продавцу (см. инструкцию ниже); если approved=false: пустая строка>"
}}

Критерии оценки:
- Цена попадает в бюджет клиента
- Площадь и количество комнат соответствуют
- Описание не вызывает подозрений

{_message_instruction(client)}"""

    try:
        import asyncio
        response = await asyncio.to_thread(model.generate_content, prompt)
        return _parse_response(response.text)
    except Exception as e:
        raise RuntimeError(f"Gemini API ошибка: {e}") from e


def _message_instruction(client: dict) -> str:
    """Инструкция для Gemini как составить сообщение продавцу."""
    template = client.get("message_template", "").strip() if client.get("message_template") else ""
    if template:
        return (
            f"Инструкция по сообщению:\n"
            f"Используй следующий шаблон как основу, при необходимости немного адаптируй под конкретное объявление:\n"
            f'"{template}"'
        )
    return (
        "Инструкция по сообщению:\n"
        "Напиши короткое (2-3 предложения) вежливое сообщение продавцу от имени риелтора на русском языке. "
        "Сообщение должно быть естественным, не шаблонным, выражать интерес к объекту."
    )


def _format_client(c: dict) -> str:
    lines = [f"Имя: {c.get('name', '—')}"]
    if c.get("district"):
        lines.append(f"Район/город: {c['district']}")
    if c.get("budget_min") or c.get("budget_max"):
        b_min = f"{c['budget_min']:,}" if c.get("budget_min") else "—"
        b_max = f"{c['budget_max']:,}" if c.get("budget_max") else "—"
        lines.append(f"Бюджет: {b_min} – {b_max} ₸")
    if c.get("area_min") or c.get("area_max"):
        lines.append(f"Площадь: {c.get('area_min','—')} – {c.get('area_max','—')} м²")
    if c.get("rooms"):
        lines.append(f"Комнат: {c['rooms']}")
    lines.append(f"Тип сделки: {'Аренда' if c.get('deal_type') == 'rent' else 'Покупка'}")
    return "\n".join(lines)


def _format_listing(l: dict) -> str:
    lines = [f"Заголовок: {l.get('title', '—')}"]
    if l.get("price"):
        lines.append(f"Цена: {l['price']:,} ₸")
    if l.get("area"):
        lines.append(f"Площадь: {l['area']} м²")
    if l.get("rooms"):
        lines.append(f"Комнат: {l['rooms']}")
    if l.get("district"):
        lines.append(f"Адрес/район: {l['district']}")
    if l.get("description"):
        lines.append(f"Описание: {l['description'][:400]}")
    lines.append(f"Ссылка: {l.get('url', '—')}")
    return "\n".join(lines)


def _parse_response(text: str) -> ListingAnalysis:
    """Парсит JSON-ответ Gemini."""
    # Убираем возможные markdown-обёртки
    clean = re.sub(r"```(?:json)?|```", "", text).strip()

    try:
        data = json.loads(clean)
        return ListingAnalysis(
            score=int(data.get("score", 0)),
            approved=bool(data.get("approved", False)),
            comment=str(data.get("comment", "")),
            message=str(data.get("message", "")),
        )
    except (json.JSONDecodeError, ValueError):
        # Fallback если Gemini вернул не чистый JSON
        return ListingAnalysis(
            score=0,
            approved=False,
            comment="Не удалось разобрать ответ Gemini",
            message="",
        )
