from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from bot.db.sqlite_manager import SQLiteManager
from bot.handlers.keyboards import (
    get_settings_keyboard,
    get_llm_keyboard,
    get_ab_toggle_keyboard,
    get_back_keyboard,
    get_cancel_edit_keyboard
)
from bot.handlers.commands import DEFAULT_META_PROMPT, DEFAULT_CONTEXT, SettingsStates

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "settings_back")
async def callback_settings_back(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    provider_name = "Gemini" if user["llm_provider"] == "gemini" else "DeepSeek"
    ab_status = "включено" if user["ab_testing_enabled"] else "выключено"

    await callback.message.edit_text(
        f"⚙️ Настройки:\n\n"
        f"LLM провайдер: {provider_name}\n"
        f"A/B тестирование: {ab_status}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "settings_llm")
async def callback_settings_llm(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    await callback.message.edit_text(
        "🔄 Выберите LLM провайдер:",
        reply_markup=get_llm_keyboard(user["llm_provider"])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("llm_"))
async def callback_select_llm(callback: CallbackQuery, db_manager: SQLiteManager):
    provider = callback.data.split("_")[1]
    user_id = callback.from_user.id

    await db_manager.update_user_setting(user_id, "llm_provider", provider)

    provider_name = "Gemini" if provider == "gemini" else "DeepSeek"
    await callback.message.edit_text(
        f"✅ LLM провайдер изменен на: {provider_name}",
        reply_markup=get_back_keyboard()
    )
    await callback.answer(f"Выбран {provider_name}")


@router.callback_query(F.data == "settings_ab")
async def callback_settings_ab(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    ab_enabled = bool(user["ab_testing_enabled"])
    await callback.message.edit_text(
        "🧪 A/B тестирование:\n\n"
        "При включении бот будет генерировать два варианта оптимизированного промпта:\n"
        "- Вариант A: temperature=0.2 (более точный)\n"
        "- Вариант B: temperature=0.7 (более креативный)\n\n"
        f"Текущий статус: {'✅ Включено' if ab_enabled else '❌ Выключено'}",
        reply_markup=get_ab_toggle_keyboard(ab_enabled)
    )
    await callback.answer()


@router.callback_query(F.data == "ab_toggle")
async def callback_ab_toggle(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    current_status = bool(user["ab_testing_enabled"])
    new_status = 1 if not current_status else 0

    await db_manager.update_user_setting(user_id, "ab_testing_enabled", new_status)

    status_text = "включено" if new_status else "выключено"
    await callback.message.edit_text(
        f"✅ A/B тестирование {status_text}",
        reply_markup=get_back_keyboard()
    )
    await callback.answer(f"A/B тестирование {status_text}")


@router.callback_query(F.data == "settings_meta")
async def callback_settings_meta(callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    current_meta = user["meta_prompt"] or DEFAULT_META_PROMPT

    await callback.message.edit_text(
        f"✏️ Текущий meta-промпт:\n\n{current_meta}\n\n"
        f"Отправьте новый meta-промпт или нажмите 'Отменить':",
        reply_markup=get_cancel_edit_keyboard()
    )

    await state.set_state(SettingsStates.editing_meta_prompt)
    await callback.answer()


@router.callback_query(F.data == "settings_context")
async def callback_settings_context(callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    current_context = user["context_prompt"] or DEFAULT_CONTEXT

    await callback.message.edit_text(
        f"📝 Текущий контекст:\n\n{current_context}\n\n"
        f"Отправьте новый контекст или нажмите 'Отменить':",
        reply_markup=get_cancel_edit_keyboard()
    )

    await state.set_state(SettingsStates.editing_context)
    await callback.answer()


@router.callback_query(F.data.startswith("ab_select_"))
async def callback_ab_select(callback: CallbackQuery, db_manager: SQLiteManager):
    variant = callback.data.split("_")[-1].upper()
    await callback.message.edit_text(
        f"✅ Выбран вариант {variant}\n\n"
        f"Вы можете:\n"
        f"- Отправить новый промпт для оптимизации\n"
        f"- Перейти в настройки через /settings\n"
        f"- Вернуться в главное меню",
        reply_markup=get_back_keyboard()
    )
    await callback.answer(f"Выбран вариант {variant}")


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    provider_name = "Gemini" if user["llm_provider"] == "gemini" else "DeepSeek"
    ab_status = "включено" if user["ab_testing_enabled"] else "выключено"

    await callback.message.edit_text(
        "👋 <b>Главное меню</b>\n\n"
        f"Текущие настройки:\n"
        f"• LLM провайдер: {provider_name}\n"
        f"• A/B тестирование: {ab_status}\n\n"
        f"<b>Что вы хотите сделать?</b>\n\n"
        f"📝 Отправьте промпт для оптимизации\n"
        f"⚙️ Используйте /settings для настройки бота\n"
        f"📖 Используйте /help для справки",
        parse_mode="HTML"
    )
    await callback.answer("Главное меню")


@router.callback_query(F.data == "cancel_edit")
async def callback_cancel_edit(callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager):
    await state.clear()
    
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    provider_name = "Gemini" if user["llm_provider"] == "gemini" else "DeepSeek"
    ab_status = "включено" if user["ab_testing_enabled"] else "выключено"

    await callback.message.edit_text(
        "❌ Редактирование отменено\n\n"
        f"⚙️ Настройки:\n\n"
        f"LLM провайдер: {provider_name}\n"
        f"A/B тестирование: {ab_status}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer("Редактирование отменено")


@router.callback_query()
async def callback_unknown(callback: CallbackQuery):
    await callback.answer("Неизвестная команда", show_alert=True)


