from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from bot.db.sqlite_manager import SQLiteManager
from bot.services.llm_client import LLMService
from bot.handlers.keyboards import (
    get_settings_keyboard, 
    get_ab_test_keyboard,
    get_back_keyboard
)

logger = logging.getLogger(__name__)

router = Router()

DEFAULT_META_PROMPT = """Ты — эксперт в prompt engineering. Твоя задача: улучшить данный промпт, сделав его максимально эффективным для LLM.

Лучшие практики для улучшения:
- Добавь роль (role-playing): укажи, кем является модель (e.g., "Ты — эксперт в X").
- Используй chain-of-thought: добавь шаги мышления (e.g., "Сначала подумай, потом ответь").
- Увеличивай specificity: добавь детали, примеры, формат вывода.
- Убери неоднозначности: используй четкие формулировки, delimiters (e.g., ### для разделов).
- Добавь constraints: укажи лимиты (e.g., "Ответь кратко", "Избегай hallucination").
- Сохрани смысл, цель и пропорциональную длину: если исходный короткий (e.g., 50 символов), не добавляй лишнего — цель в эффективности, не в объёме.
- Сделай структурированным: используй нумерованные списки, заголовки.

Few-shot примеры:

Пример 1 (исходный: короткий):
Исходный: "Суммируй текст"
Улучшенный: "Ты — эксперт в суммаризации. Возьми этот текст: [вставь текст]. Составь краткий summary: сначала выдели ключевые точки, затем напиши coherent абзац. Формат: - Ключевые точки: 1. ... 2. ... - Summary: [текст]. Избегай добавления новой информации."

Пример 2 (исходный: средний):
Исходный: "Напиши историю о собаке"
Улучшенный: "Ты — креативный писатель. Напиши короткую историю о собаке, которая находит приключения. Структура: 1. Введение (представь персонажа). 2. Середина (конфликт). 3. Конец (разрешение). Длина: 200-300 слов. Используй vivid язык, но избегай клише."

Теперь улучши этот промпт: [вставь исходный промпт здесь].

Верни только улучшенный промпт, без объяснений или дополнительного текста."""

DEFAULT_CONTEXT = """Ты опытный специалист по оптимизации промптов для языковых моделей. Твоя задача - улучшать промпты пользователей, делая их более эффективными и понятными для LLM."""


class SettingsStates(StatesGroup):
    editing_meta_prompt = State()
    editing_context = State()


@router.message(Command("start"))
async def cmd_start(message: Message, db_manager: SQLiteManager):
    user_id = message.from_user.id
    await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    await message.answer(
        "👋 Привет! Я бот для оптимизации промптов.\n\n"
        "Отправь мне любой промпт, и я улучшу его с помощью meta-prompting.\n\n"
        "Доступные команды:\n"
        "/settings - настройки бота\n"
        "/help - справка",
        reply_markup=get_settings_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Справка по использованию бота:\n\n"
        "1. Просто отправь мне любой промпт, и я его оптимизирую\n"
        "2. Используй /settings для настройки:\n"
        "   - Выбор LLM (Gemini или DeepSeek)\n"
        "   - Включение/выключение A/B тестирования\n"
        "   - Редактирование meta-промпта\n"
        "   - Редактирование контекста\n\n"
        "A/B тестирование позволяет сравнить два варианта оптимизации:\n"
        "- Вариант A: более точный и детерминистичный (temperature=0.2)\n"
        "- Вариант B: более креативный (temperature=0.7)"
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, db_manager: SQLiteManager):
    user_id = message.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    provider_name = "Gemini" if user["llm_provider"] == "gemini" else "DeepSeek"
    ab_status = "включено" if user["ab_testing_enabled"] else "выключено"

    await message.answer(
        f"⚙️ Настройки:\n\n"
        f"LLM провайдер: {provider_name}\n"
        f"A/B тестирование: {ab_status}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )


@router.message(SettingsStates.editing_meta_prompt)
async def handle_meta_prompt_edit(message: Message, state: FSMContext, db_manager: SQLiteManager):
    user_id = message.from_user.id
    new_meta_prompt = message.text

    await db_manager.update_user_setting(user_id, "meta_prompt", new_meta_prompt)
    await state.clear()

    await message.answer(
        "✅ Meta-промпт успешно обновлен!\n\n"
        "Используйте /settings для дальнейших настроек.",
        reply_markup=get_back_keyboard()
    )


@router.message(SettingsStates.editing_context)
async def handle_context_edit(message: Message, state: FSMContext, db_manager: SQLiteManager):
    user_id = message.from_user.id
    new_context = message.text

    await db_manager.update_user_setting(user_id, "context_prompt", new_context)
    await state.clear()

    await message.answer(
        "✅ Контекст успешно обновлен!\n\n"
        "Используйте /settings для дальнейших настроек.",
        reply_markup=get_back_keyboard()
    )


@router.message(F.text, ~F.text.startswith("/"))
async def handle_prompt(message: Message, db_manager: SQLiteManager, llm_service: LLMService):
    user_id = message.from_user.id
    user_prompt = message.text
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    processing_msg = await message.answer("🔄 Обрабатываю промпт...")

    try:
        provider = user["llm_provider"]
        meta_prompt = user["meta_prompt"] or DEFAULT_META_PROMPT
        context_prompt = user["context_prompt"] or DEFAULT_CONTEXT
        ab_enabled = user["ab_testing_enabled"]

        if ab_enabled:
            await processing_msg.edit_text("🔄 Генерирую варианты A и B...")

            variant_a = await llm_service.optimize_prompt(
                user_prompt,
                meta_prompt,
                context_prompt,
                provider,
                temperature=0.2
            )

            variant_b = await llm_service.optimize_prompt(
                user_prompt,
                meta_prompt,
                context_prompt,
                provider,
                temperature=0.7
            )

            original_length = len(user_prompt)
            length_a = len(variant_a)
            length_b = len(variant_b)

            await processing_msg.delete()
            await message.answer(
                f"📊 <b>Вариант A</b> (temperature=0.2, более точный):\n\n"
                f"{variant_a}\n\n"
                f"Длина: {original_length} → {length_a} символов "
                f"({((length_a - original_length) / original_length * 100):+.1f}%)",
                parse_mode="HTML"
            )

            await message.answer(
                f"📊 <b>Вариант B</b> (temperature=0.7, более креативный):\n\n"
                f"{variant_b}\n\n"
                f"Длина: {original_length} → {length_b} символов "
                f"({((length_b - original_length) / original_length * 100):+.1f}%)",
                parse_mode="HTML",
                reply_markup=get_ab_test_keyboard()
            )

        else:
            optimized = await llm_service.optimize_prompt(
                user_prompt,
                meta_prompt,
                context_prompt,
                provider
            )

            original_length = len(user_prompt)
            optimized_length = len(optimized)
            original_words = len(user_prompt.split())
            optimized_words = len(optimized.split())

            await processing_msg.delete()

            await message.answer(
                f"✨ <b>Оптимизированный промпт:</b>\n\n"
                f"{optimized}\n\n"
                f"📈 <b>Метрики:</b>\n"
                f"Длина: {original_length} → {optimized_length} символов "
                f"({((optimized_length - original_length) / original_length * 100):+.1f}%)\n"
                f"Слова: {original_words} → {optimized_words} "
                f"({((optimized_words - original_words) / original_words * 100):+.1f}%)",
                parse_mode="HTML",
                reply_markup=get_back_keyboard()
            )

    except ValueError as e:
        await processing_msg.edit_text(
            f"❌ Ошибка: {str(e)}\n\n"
            f"Проверьте настройки в /settings"
        )
    except Exception as e:
        error_code = type(e).__name__
        logger.error(f"Ошибка при обработке промпта: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"❌ Произошла ошибка при обработке промпта.\n\n"
            f"Код ошибки: {error_code}\n"
            f"Попробуйте повторить запрос позже."
        )

