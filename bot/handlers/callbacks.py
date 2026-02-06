from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from bot.db.sqlite_manager import SQLiteManager
from bot.handlers.keyboards import (
    get_settings_keyboard,
    get_customization_keyboard,
    get_temperature_keyboard,
    get_llm_keyboard,
    get_llm_error_keyboard,
    get_back_keyboard,
    get_cancel_edit_keyboard,
    get_mode_keyboard,
    get_result_nav_keyboard,
    get_agent_result_keyboard,
    get_agent_questions_keyboard,
    get_agent_question_single_keyboard,
    get_preference_style_keyboard,
    get_preference_goal_keyboard,
    get_preference_format_keyboard,
)
from bot.handlers.commands import (
    DEFAULT_META_PROMPT,
    DEFAULT_CONTEXT,
    SettingsStates,
    OnboardingStates,
    AgentStates,
    PREFERENCE_GOAL_LABELS,
    AGENT_SYSTEM_PROMPT_BASE,
    _format_agent_reply_for_telegram,
    _parse_agent_reply,
    _parse_agent_questions,
    _get_previous_agent_prompt,
    _agent_metrics_line,
    _rouge_line,
    _rouge_scores,
    _why_better_line,
    _html_escape,
    _send_long_message,
    _send_agent_reply_safe,
    _is_llm_provider_error,
    QUESTIONS_OPEN,
    _format_preferences_for_prompt,
)

PROVIDER_NAMES = {
    "deepseek": "DeepSeek",
    "openai": "ChatGPT",
    "gemini": "Gemini",
    "grok": "Grok 4 Fast (xAI)",
    "nemo": "Mistral Nemo",
    "mimo": "Xiaomi Mimo V2 Flash",
    "trinity": "Trinity Large (free)",
    "gpt5nano": "GPT-5 Nano",
    "deepseek_r1t": "DeepSeek R1T Chimera (free)",
    "qwen3": "Qwen3 235B",
}
MODE_NAMES = {"simple": "простой", "agent": "агент"}

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

    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")

    await callback.message.edit_text(
        f"⚙️ Настройки:\n\n"
        f"LLM: {provider_name} | Режим: {mode_name}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "settings_customization")
async def callback_settings_customization(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    temp = float(user.get("temperature", 0.4))
    await callback.message.edit_text(
        "⚙️ Кастомизация\n\n"
        "Предпочтения, meta-промпт, контекст и температура модели.",
        reply_markup=get_customization_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "customization_back")
async def callback_customization_back(callback: CallbackQuery, db_manager: SQLiteManager):
    await callback.message.edit_text(
        "⚙️ Кастомизация\n\n"
        "Предпочтения, meta-промпт, контекст и температура модели.",
        reply_markup=get_customization_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "settings_temperature")
async def callback_settings_temperature(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    temp = float(user.get("temperature", 0.4))
    await callback.message.edit_text(
        "🌡 Температура влияет на ответы модели:\n\n"
        "• Очень низкая (0.1) — максимально стабильные и предсказуемые ответы, почти без креативности.\n"
        "• Низкая (0.3–0.4) — стабильнее и предсказуемее, лучше держит формат [PROMPT]/[QUESTIONS].\n"
        "• Средняя (0.5) — баланс между стабильностью и разнообразием.\n"
        "• Высокая (0.6–0.7) — больше креативных формулировок, иногда отклоняется от формата.\n"
        "• Очень высокая (0.9) — максимум разнообразия, возможны сильные отклонения от формата и стиля.\n\n"
        f"Текущая: {temp}",
        reply_markup=get_temperature_keyboard(temp)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("temp_"))
async def callback_temp_set(callback: CallbackQuery, db_manager: SQLiteManager):
    try:
        val = float(callback.data.replace("temp_", ""))
    except ValueError:
        await callback.answer()
        return
    # Разрешённые значения температуры (в том числе 0.1 и 0.9)
    if val not in (0.1, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9):
        await callback.answer()
        return
    user_id = callback.from_user.id
    await db_manager.update_user_setting(user_id, "temperature", val)
    await callback.message.edit_text(
        f"🌡 Температура: {val} сохранена.",
        reply_markup=get_temperature_keyboard(val)
    )
    await callback.answer(f"Температура: {val}")


GOAL_SELECT_TEXT = (
    "Для чего ты чаще используешь ИИ?\n\n"
    "Выбери до 4 вариантов, затем нажми «Готово»."
)


@router.callback_query(F.data == "settings_preferences")
async def callback_settings_preferences(
    callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager
):
    await state.clear()
    await callback.message.edit_text(
        "👤 Предпочтения помогут боту подстроиться под тебя.\n\n"
        "Как тебе удобнее получать ответы?",
        reply_markup=get_preference_style_keyboard()
    )
    await callback.answer()


def _parse_goal_preference(value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [g.strip() for g in value.split(",") if g.strip()]


@router.callback_query(F.data.startswith("pref_style_"))
async def callback_pref_style(
    callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager
):
    style = callback.data.replace("pref_style_", "")
    user_id = callback.from_user.id
    await db_manager.update_user_setting(user_id, "preference_style", style)
    user = await db_manager.get_or_create_user(
        user_id, DEFAULT_META_PROMPT, DEFAULT_CONTEXT
    )
    selected = _parse_goal_preference(user.get("preference_goal"))
    await state.set_state(OnboardingStates.selecting_goals)
    await state.update_data(selected_goals=selected)
    await callback.message.edit_text(
        GOAL_SELECT_TEXT,
        reply_markup=get_preference_goal_keyboard(selected)
    )
    await callback.answer()


@router.callback_query(
    OnboardingStates.selecting_goals, F.data.startswith("pref_goal_toggle_")
)
async def callback_pref_goal_toggle(
    callback: CallbackQuery, state: FSMContext
):
    goal_id = callback.data.replace("pref_goal_toggle_", "")
    data = await state.get_data()
    selected: list = list(data.get("selected_goals") or [])
    if goal_id in selected:
        selected.remove(goal_id)
    else:
        if len(selected) >= 4:
            await callback.answer("Можно выбрать не более 4 вариантов", show_alert=True)
            return
        selected.append(goal_id)
    await state.update_data(selected_goals=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_preference_goal_keyboard(selected)
    )
    label = PREFERENCE_GOAL_LABELS.get(goal_id, goal_id)
    await callback.answer(f"Выбрано: {len(selected)} из 4")


@router.callback_query(OnboardingStates.selecting_goals, F.data == "pref_goal_done")
async def callback_pref_goal_done(
    callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager
):
    data = await state.get_data()
    selected: list = data.get("selected_goals") or []
    await state.clear()
    user_id = callback.from_user.id
    value = ",".join(selected) if selected else ""
    await db_manager.update_user_setting(user_id, "preference_goal", value)
    await callback.message.edit_text(
        "Какой формат промптов тебе ближе?",
        reply_markup=get_preference_format_keyboard()
    )
    await callback.answer("Цели сохранены")


@router.callback_query(F.data.startswith("pref_format_"))
async def callback_pref_format(callback: CallbackQuery, db_manager: SQLiteManager):
    fmt = callback.data.replace("pref_format_", "")
    user_id = callback.from_user.id
    await db_manager.update_user_setting(user_id, "preference_format", fmt)
    await callback.message.edit_text(
        "✅ Предпочтения сохранены. Можешь отправить промпт или зайти в настройки.",
        reply_markup=get_back_keyboard()
    )
    await callback.answer("Предпочтения сохранены")


@router.callback_query(F.data == "settings_mode")
async def callback_settings_mode(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    mode = user.get("mode", "simple")
    await callback.message.edit_text(
        "🔄 Режим бота:\n\n"
        "• Простой — отправь промпт, получишь улучшенный вариант (без памяти).\n"
        "• Агент — диалог с памятью: агент помогает создать промпт, задаёт уточняющие вопросы.\n\n"
        f"Текущий режим: {MODE_NAMES.get(mode, mode)}",
        reply_markup=get_mode_keyboard(mode)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mode_"))
async def callback_select_mode(callback: CallbackQuery, db_manager: SQLiteManager):
    mode = callback.data.split("_")[1]
    user_id = callback.from_user.id
    await db_manager.update_user_setting(user_id, "mode", mode)
    if mode == "agent":
        await db_manager.clear_agent_history(user_id)
    await callback.message.edit_text(
        f"✅ Режим изменён на: {MODE_NAMES.get(mode, mode)}",
        reply_markup=get_back_keyboard()
    )
    await callback.answer(f"Режим: {MODE_NAMES.get(mode, mode)}")


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

    provider_name = PROVIDER_NAMES.get(provider, provider)
    await callback.message.edit_text(
        f"✅ LLM провайдер изменен на: {provider_name}",
        reply_markup=get_back_keyboard()
    )
    await callback.answer(f"Выбран {provider_name}")


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


@router.callback_query(F.data == "nav_main")
async def callback_nav_main(callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.clear()
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")
    await callback.message.answer(
        "👋 <b>Главное меню</b>\n\n"
        f"• LLM: {provider_name} | Режим: {mode_name}\n\n"
        f"📝 Отправьте промпт для оптимизации\n"
        f"⚙️ /settings — настройки\n"
        f"📖 /help — справка",
        parse_mode="HTML",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer("Главное меню")


@router.callback_query(F.data == "nav_settings")
async def callback_nav_settings(callback: CallbackQuery, db_manager: SQLiteManager):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")
    await callback.message.answer(
        f"⚙️ Настройки\n\n"
        f"LLM: {provider_name} | Режим: {mode_name}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer("Настройки")


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext, db_manager: SQLiteManager):
    await state.clear()
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")

    try:
        await callback.message.edit_text(
            "👋 <b>Главное меню</b>\n\n"
            f"• LLM: {provider_name} | Режим: {mode_name}\n\n"
            f"📝 Отправьте промпт для оптимизации\n"
            f"⚙️ /settings — настройки\n"
            f"📖 /help — справка",
            parse_mode="HTML",
            reply_markup=get_settings_keyboard()
        )
    except Exception:
        pass
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

    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")

    await callback.message.edit_text(
        "❌ Редактирование отменено\n\n"
        f"⚙️ Настройки: LLM: {provider_name} | Режим: {mode_name}\n\n"
        f"Выберите действие:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer("Редактирование отменено")


@router.callback_query(AgentStates.answering_questions, F.data.startswith("aq_"))
async def callback_agent_question_answer(
    callback: CallbackQuery,
    state: FSMContext,
    db_manager: SQLiteManager,
    llm_service,
):
    raw = callback.data
    if raw == "aq_done":
        await callback.answer("Формирую итоговый промпт…")
        data = await state.get_data()
        original_request = data.get("agent_original_request") or ""
        questions = data.get("agent_questions") or []
        answers = data.get("agent_answers") or {}
        provider = data.get("agent_provider") or "gemini"
        prefs = data.get("agent_prefs") or ""
        lines = []
        for q_idx, q in enumerate(questions):
            selected = answers.get(q_idx)
            opts = q.get("options") or []
            # Поддержка как старого формата (один индекс), так и нового (список индексов)
            if isinstance(selected, list):
                indices = [i for i in selected if isinstance(i, int) and 0 <= i < len(opts)]
            elif isinstance(selected, int):
                indices = [selected] if 0 <= selected < len(opts) else []
            else:
                indices = []
            if not indices:
                opt_text = "не указано"
            else:
                chosen = [opts[i] for i in indices]
                opt_text = ", ".join(chosen)
            lines.append(f"{q_idx + 1}. {q.get('question', '')}: {opt_text}")
        answers_text = "\n".join(lines)
        system_prompt = (prefs + "\n\n" + AGENT_SYSTEM_PROMPT_BASE) if prefs else AGENT_SYSTEM_PROMPT_BASE
        user_content = (
            f"Исходный запрос пользователя:\n{original_request}\n\n"
            f"Ответы на уточняющие вопросы:\n{answers_text}\n\n"
            "Сформируй итоговый промпт и верни его в [PROMPT] и [/PROMPT] (каждый тег на отдельной строке). Только промпт, без лишнего текста после [/PROMPT]."
        )
        await callback.message.edit_text("🔄 Формирую промпт...")
        await state.clear()
        user_id = callback.from_user.id
        user = await db_manager.get_or_create_user(
            user_id, DEFAULT_META_PROMPT, DEFAULT_CONTEXT
        )
        temperature = float(user.get("temperature", 0.4))
        try:
            reply = await llm_service.chat_with_history(
                user_content=user_content,
                history=[],
                system_prompt=system_prompt,
                provider=provider,
                temperature=temperature,
            )
            user_msg_for_history = original_request + "\n\nОтветы на вопросы:\n" + answers_text
            await db_manager.add_agent_message(user_id, "user", user_msg_for_history)
            await db_manager.add_agent_message(user_id, "assistant", reply)
            intro, prompt_block, outro = _parse_agent_reply(reply)
            extra = []
            if prompt_block.strip():
                metrics_line = _agent_metrics_line(original_request, prompt_block)
                if metrics_line:
                    extra.append(metrics_line)
                rouge_orig = _rouge_line("Похожесть на исходный запрос", original_request, prompt_block)
                if rouge_orig:
                    extra.append(rouge_orig)
                scores = _rouge_scores(original_request, prompt_block)
                rouge_r1 = scores[0] if scores else None
                why_line = _why_better_line(original_request, prompt_block, rouge_r1)
                if why_line:
                    extra.append(why_line)
            await _send_agent_reply_safe(
                callback.message,
                intro=intro or "",
                prompt_block=prompt_block or "",
                outro=outro or "",
                extra_lines=extra,
                reply_markup=get_agent_result_keyboard(),
            )
        except Exception as e:
            logger.exception("Ошибка при формировании промпта из ответов: %s", e)
            if _is_llm_provider_error(e):
                pname = PROVIDER_NAMES.get(provider, provider)
                text = (
                    f"❌ Сейчас не удаётся обратиться к модели <b>{pname}</b>.\n\n"
                    "Часто это из‑за ограничений по региону или временной недоступности провайдера. "
                    "Переключитесь на другую модель в настройках или нажмите кнопку ниже."
                )
                await callback.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_llm_error_keyboard(),
                )
            else:
                await callback.message.answer(
                    "❌ Не удалось сформировать промпт. Попробуйте ещё раз или отправьте новый запрос."
                )
        return
    if raw == "aq_skip":
        # Пользователь просит сразу сформировать промпт без дальнейших вопросов.
        data = await state.get_data()
        original_request = data.get("agent_original_request") or ""
        provider = data.get("agent_provider") or "gemini"
        prefs = data.get("agent_prefs") or ""
        system_prompt = (prefs + "\n\n" + AGENT_SYSTEM_PROMPT_BASE) if prefs else AGENT_SYSTEM_PROMPT_BASE
        user_content = (
            "Пользователь хочет получить итоговый промпт СРАЗУ, без дополнительных уточняющих вопросов.\n"
            "Сформируй промпт только на основе этого запроса, не добавляя новых деталей:\n\n"
            f"{original_request}\n\n"
            "Верни промпт в [PROMPT] и [/PROMPT] (каждый тег на отдельной строке). Только промпт, без лишнего текста после [/PROMPT]."
        )
        await callback.message.edit_text("🔄 Формирую промпт без дополнительных вопросов...")
        await state.clear()
        user_id = callback.from_user.id
        user = await db_manager.get_or_create_user(
            user_id, DEFAULT_META_PROMPT, DEFAULT_CONTEXT
        )
        temperature = float(user.get("temperature", 0.4))
        try:
            reply = await llm_service.chat_with_history(
                user_content=user_content,
                history=[],
                system_prompt=system_prompt,
                provider=provider,
                temperature=temperature,
            )
            await db_manager.add_agent_message(user_id, "user", original_request)
            await db_manager.add_agent_message(user_id, "assistant", reply)
            intro, prompt_block, outro = _parse_agent_reply(reply)
            extra = []
            if prompt_block.strip():
                metrics_line = _agent_metrics_line(original_request, prompt_block)
                if metrics_line:
                    extra.append(metrics_line)
                rouge_orig = _rouge_line("Похожесть на исходный запрос", original_request, prompt_block)
                if rouge_orig:
                    extra.append(rouge_orig)
                scores = _rouge_scores(original_request, prompt_block)
                rouge_r1 = scores[0] if scores else None
                why_line = _why_better_line(original_request, prompt_block, rouge_r1)
                if why_line:
                    extra.append(why_line)
            await _send_agent_reply_safe(
                callback.message,
                intro=intro or "",
                prompt_block=prompt_block or "",
                outro=outro or "",
                extra_lines=extra,
                reply_markup=get_agent_result_keyboard(),
            )
        except Exception as e:
            logger.exception("Ошибка при формировании промпта без вопросов: %s", e)
            if _is_llm_provider_error(e):
                pname = PROVIDER_NAMES.get(provider, provider)
                text = (
                    f"❌ Сейчас не удаётся обратиться к модели <b>{pname}</b>.\n\n"
                    "Часто это из‑за ограничений по региону или временной недоступности провайдера. "
                    "Переключитесь на другую модель в настройках или нажмите кнопку ниже."
                )
                await callback.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_llm_error_keyboard(),
                )
            else:
                await callback.message.answer(
                    "❌ Не удалось сформировать промпт. Попробуйте ещё раз или отправьте новый запрос."
                )
        return
    parts = raw.split("_")
    if len(parts) != 3 or parts[0] != "aq":
        await callback.answer()
        return
    try:
        q_idx = int(parts[1])
        opt_idx = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    data = await state.get_data()
    questions = data.get("agent_questions") or []
    answers = data.get("agent_answers") or {}
    if q_idx < 0 or q_idx >= len(questions):
        await callback.answer()
        return

    # Множественный выбор: при повторном нажатии по тому же варианту — снимаем выбор.
    current = answers.get(q_idx)
    if isinstance(current, list):
        selected = list(current)
    elif isinstance(current, int):
        selected = [current]
    else:
        selected = []

    if opt_idx in selected:
        selected.remove(opt_idx)
    else:
        selected.append(opt_idx)

    answers[q_idx] = selected
    await state.update_data(agent_answers=answers)
    try:
        q = questions[q_idx]
        is_last = q_idx == len(questions) - 1
        await callback.message.edit_reply_markup(
            reply_markup=get_agent_question_single_keyboard(q_idx, q, answers, is_last)
        )
    except Exception:
        pass
    await callback.answer("Выбрано")


@router.callback_query(F.data == "agent_accept_prompt")
async def callback_agent_accept_prompt(callback: CallbackQuery, db_manager: SQLiteManager):
    user_id = callback.from_user.id
    await db_manager.clear_agent_history(user_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=get_result_nav_keyboard())
    except Exception:
        pass
    await callback.answer("Промпт принят. Следующее сообщение — новый диалог.")


@router.callback_query(F.data == "agent_continue")
async def callback_agent_continue(
    callback: CallbackQuery,
    db_manager: SQLiteManager,
    llm_service,
    state: FSMContext,
):
    """При нажатии 'Уточнить ещё' агент анализирует текущий промпт и задаёт уточняющие вопросы."""
    user_id = callback.from_user.id
    user = await db_manager.get_or_create_user(
        user_id, DEFAULT_META_PROMPT, DEFAULT_CONTEXT
    )
    
    # Убираем клавиатуру под сообщением
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    await callback.answer("Анализирую промпт и готовлю уточняющие вопросы...")
    
    # Получаем историю и последний промпт
    history = await db_manager.get_agent_history(user_id)
    previous_agent_prompt = _get_previous_agent_prompt(history)
    
    if not previous_agent_prompt:
        await callback.message.answer(
            "❌ Не найден текущий промпт для уточнения.\n\n"
            "Просто напиши свой запрос или уточнение, и я помогу."
        )
        return
    
    # Формируем запрос агенту: проанализировать промпт и задать уточняющие вопросы
    prefs_text = _format_preferences_for_prompt(user)
    system_prompt = (prefs_text + "\n\n" + AGENT_SYSTEM_PROMPT_BASE) if prefs_text else AGENT_SYSTEM_PROMPT_BASE
    
    user_content = (
        "Пользователь хочет уточнить и улучшить этот промпт:\n\n"
        f"{previous_agent_prompt}\n\n"
        "Проанализируй промпт и определи, какие уточнения нужны для его улучшения. "
        "Задай уточняющие вопросы (в формате [QUESTIONS]...[/QUESTIONS]) или, если промпт уже достаточно детален, "
        "предложи улучшенный вариант (в формате [PROMPT]...[/PROMPT])."
    )
    
    provider = user["llm_provider"] or "trinity"
    temperature = float(user.get("temperature", 0.4))
    
    processing_msg = await callback.message.answer("🔄 Анализирую промпт и готовлю вопросы...")
    
    try:
        reply = await llm_service.chat_with_history(
            user_content=user_content,
            history=history,
            system_prompt=system_prompt,
            provider=provider,
            temperature=temperature,
        )
        
        # Сохраняем в историю
        await db_manager.add_agent_message(user_id, "user", "Хочу уточнить промпт")
        await db_manager.add_agent_message(user_id, "assistant", reply)
        
        await processing_msg.delete()
        
        # Проверяем, задал ли агент вопросы
        questions = _parse_agent_questions(reply)
        if questions:
            # Агент задал вопросы - показываем их
            intro = reply.split(QUESTIONS_OPEN)[0].strip() if QUESTIONS_OPEN in reply else ""
            await state.set_state(AgentStates.answering_questions)
            await state.update_data(
                agent_original_request=previous_agent_prompt,
                agent_questions=questions,
                agent_answers={},
                agent_provider=provider,
                agent_prefs=prefs_text or "",
            )
            answers = {}
            for i, q in enumerate(questions):
                text = _html_escape(q["question"])
                if intro and i == 0:
                    text = _html_escape(intro) + "\n\n" + text
                await callback.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_agent_question_single_keyboard(
                        i, q, answers, i == len(questions) - 1
                    ),
                )
            # Добавляем подсказку после последнего вопроса
            await callback.message.answer(
                "💡 Или напиши своё уточнение текстом — я обработаю его.",
                reply_markup=None
            )
        else:
            # Агент дал улучшенный промпт или комментарий
            intro, prompt_block, outro = _parse_agent_reply(reply)
            extra = []
            if prompt_block.strip():
                metrics_line = _agent_metrics_line(previous_agent_prompt, prompt_block)
                if metrics_line:
                    extra.append(metrics_line)
                rouge_prev = _rouge_line("Предыдущий вариант → улучшенный", previous_agent_prompt, prompt_block)
                if rouge_prev:
                    extra.append(rouge_prev)
                scores_prev = _rouge_scores(previous_agent_prompt, prompt_block)
                rouge_r1 = scores_prev[0] if scores_prev else None
                why_line = _why_better_line(previous_agent_prompt, prompt_block, rouge_r1)
                if why_line:
                    extra.append(why_line)
            if not prompt_block.strip() and outro.strip():
                outro = outro.strip() + "\n\n💡 Можешь написать своё уточнение текстом, и я обработаю его."
            elif not prompt_block.strip():
                outro = "💡 Можешь написать своё уточнение текстом, и я обработаю его."
            await _send_agent_reply_safe(
                callback.message,
                intro=intro or "",
                prompt_block=prompt_block or "",
                outro=outro or "",
                extra_lines=extra,
                reply_markup=get_agent_result_keyboard(),
            )
    except Exception as e:
        logger.exception("Ошибка при анализе промпта для уточнения: %s", e)
        await processing_msg.delete()
        if _is_llm_provider_error(e):
            pname = PROVIDER_NAMES.get(provider, provider)
            text = (
                f"❌ Сейчас не удаётся обратиться к модели <b>{pname}</b>.\n\n"
                "Часто это из‑за ограничений по региону или временной недоступности провайдера. "
                "Переключитесь на другую модель в настройках или нажмите кнопку ниже."
            )
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_llm_error_keyboard(),
            )
        else:
            await callback.message.answer(
                "❌ Не удалось проанализировать промпт. "
                "Попробуй написать своё уточнение текстом — я обработаю его."
            )


@router.callback_query()
async def callback_unknown(callback: CallbackQuery):
    await callback.answer("Неизвестная команда", show_alert=True)


