from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import logging
import re

TELEGRAM_MAX_MESSAGE_LENGTH = 4096

from bot.db.sqlite_manager import SQLiteManager
from bot.services.llm_client import LLMService
from bot.handlers.keyboards import (
    get_settings_keyboard,
    get_back_keyboard,
    get_result_nav_keyboard,
    get_agent_result_keyboard,
    get_agent_question_single_keyboard,
    get_llm_error_keyboard,
    get_preference_style_keyboard,
    get_preference_goal_keyboard,
    get_preference_format_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()

DEFAULT_META_PROMPT = """Ты — эксперт в prompt engineering. Задача: улучшить промпт, сделав его максимально кратким, плотным и эффективным для LLM.

Правила:
- Сохрани смысл и цель исходного без добавления новых требований.
- Для коротких исходных (<200 символов): целевая длина 80–150 слов.
- Обязательно:
  • Добавь роль ("Ты — эксперт/критик в ...").
  • 1–2 шага мышления (например, "Сначала проанализируй, потом ответь").
  • Минимальный или свободный формат вывода (без жёстких заголовков и списков).
  • Ограничения: только объективность и опора на данные.
- Формулировки делай лаконичными, разговорными, без "воды" и излишних уточнений.
- Не добавляй лишние разделы, рекомендации или тон, если их нет в исходном.

Улучши этот промпт: [вставь исходный здесь].

Верни ТОЛЬКО улучшенный промпт без объяснений и лишнего текста."""

DEFAULT_CONTEXT = """Ты опытный специалист по оптимизации промптов для языковых моделей. Твоя задача - улучшать промпты пользователей, делая их более эффективными и понятными для LLM."""

AGENT_SYSTEM_PROMPT_BASE = """Ты — помощник по созданию и улучшению промптов для языковых моделей. Общайся на русском. Ты не выполняешь задачи из промпта (не вычитываешь эссе, не анализируешь код) — только формулировки промптов.

Сценарий ответа:

Шаг 1 — Оцени сложность запроса:
• Простая: цель и контекст ясны (одна задача, понятная аудитория/формат) → 0 вопросов, сразу [PROMPT].
• Средняя: не хватает 1–2 уточнений (аудитория, тон, объём) → 1–2 вопроса в [QUESTIONS].
• Сложная: неоднозначная цель, много аспектов, новая тема → 3–5 вопросов в [QUESTIONS].

Шаг 2 — Реши, нужны ли вопросы: если пользователь уже подробно описал задачу, формат и стиль — не задавай вопросов, сразу верни [PROMPT]. Вопросы задавай только когда реально не хватает данных для точного промпта.

Отдельный сценарий: если в запросе явно дан текущий промпт и далее текст с уточнениями/правками к нему, это НЕ новый промпт, а правка существующего. В таком случае:
• учитывай исходную цель и предыдущий вариант промпта;
• обнови формулировки с учётом новых уточнений;
• по возможности сохраняй структуру и формат прошлого варианта;
• не игнорируй предыдущий промпт и не генерируй промпт “с нуля”.

Шаг 3 — Формат ответа (обязательно один из двух):

1) Готовый промпт — разметка [PROMPT] и [/PROMPT] (каждый тег на отдельной строке). До [PROMPT] — краткий комментарий, после [/PROMPT] — уточнения если нужно.

2) Уточняющие вопросы — разметка [QUESTIONS] и [/QUESTIONS]. Под каждым вопросом сразу строки вариантов с дефисом "- " (или "* "). Без вариантов вопросы не покажутся. Пример:
[QUESTIONS]
1. Какой объём анализа нужен?
- краткий обзор
- детальный разбор
- только выводы
2. Для кого промпт?
- для себя
- для команды
- для широкой аудитории
[/QUESTIONS]
Варианты до 40 символов, 2–5 на вопрос.

Запрещено: просить прислать эссе, код, текст. Разрешено: черновик промпта, уточнение цели/аудитории/формата, правки готового промпта."""

PREFERENCE_STYLE_LABELS = {"precise": "точные, по делу", "balanced": "сбалансированные", "creative": "развёрнутые с примерами"}
PREFERENCE_GOAL_LABELS = {
    "code": "код и техника",
    "study": "учёба и образование",
    "creative": "тексты и креатив",
    "analysis": "анализ данных",
    "work": "работа и бизнес",
    "research": "исследования",
    "writing": "письмо и редактура",
    "hobby": "хобби и развлечения",
    "learning": "самообразование",
    "other": "разное",
}
PREFERENCE_GOAL_IDS = tuple(PREFERENCE_GOAL_LABELS.keys())
PREFERENCE_FORMAT_LABELS = {"short": "короткие и чёткие", "structured": "структурированные", "detailed": "подробные с инструкциями"}


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PROMPT_OPEN = "[PROMPT]"
PROMPT_CLOSE = "[/PROMPT]"
QUESTIONS_OPEN = "[QUESTIONS]"
QUESTIONS_CLOSE = "[/QUESTIONS]"


def _parse_agent_questions(reply: str) -> list[dict] | None:
    """Извлекает список вопросов из блока [QUESTIONS]...[/QUESTIONS]. Если у вопроса нет вариантов — подставляется «Пропустить»."""
    if QUESTIONS_OPEN not in reply or QUESTIONS_CLOSE not in reply:
        return None
    _, rest = reply.split(QUESTIONS_OPEN, 1)
    block, _ = rest.split(QUESTIONS_CLOSE, 1)
    block = block.strip()
    if not block:
        return None
    questions = []
    current_q = None
    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\d+\.\s*(.+)$", line)
        if m:
            if current_q is not None:
                if not current_q.get("options"):
                    current_q["options"] = ["Пропустить"]
                questions.append(current_q)
            current_q = {"question": m.group(1).strip(), "options": []}
        elif (line.startswith("-") or line.startswith("*")) and current_q is not None:
            opt = line.lstrip("-*").strip()
            if opt:
                current_q["options"].append(opt)
    if current_q is not None:
        if not current_q.get("options"):
            current_q["options"] = ["Пропустить"]
        questions.append(current_q)
    return questions if questions else None


def _parse_agent_reply(reply: str) -> tuple[str, str, str]:
    """Возвращает (intro, prompt_block, outro). Блок промпта — между [PROMPT]...[/PROMPT] или в ```...```."""
    if PROMPT_OPEN in reply:
        before, rest = reply.split(PROMPT_OPEN, 1)
        if PROMPT_CLOSE in rest:
            prompt_block, after = rest.split(PROMPT_CLOSE, 1)
            return before.strip(), prompt_block.strip(), after.strip()
        return before.strip(), rest.strip(), ""
    if "```" in reply:
        parts = reply.split("```", 2)
        if len(parts) >= 3:
            intro = parts[0].strip()
            prompt_block = parts[1].lstrip().lstrip("prompt\n").lstrip()
            outro = (parts[2] if len(parts) > 2 else "").strip()
            return intro, prompt_block, outro
    return reply.strip(), "", ""


def _get_previous_agent_prompt(history: list[dict]) -> str:
    """Возвращает последний промпт агента (блок между [PROMPT]...[/PROMPT]) из истории или пустую строку."""
    for msg in reversed(history):
        if msg.get("role") == "assistant" and msg.get("content"):
            _, prev_block, _ = _parse_agent_reply(msg["content"])
            if prev_block and prev_block.strip():
                return prev_block.strip()
    return ""


def _format_agent_reply_for_telegram(reply: str) -> str:
    """Разбивает ответ агента на обычный текст и блок промпта; промпт — blockquote+pre."""
    intro, prompt_block, outro = _parse_agent_reply(reply)
    out = _html_escape(intro) if intro else ""
    if prompt_block:
        out += f"\n\n<blockquote><pre>{_html_escape(prompt_block)}</pre></blockquote>"
    if outro:
        out += "\n\n" + _html_escape(outro)
    return out.strip() or _html_escape(reply)


def _agent_metrics_line(original: str, optimized: str) -> str | None:
    """Строка метрик длины (символы и слова) для ответа агента. Если optimized пустой — None."""
    if not optimized.strip():
        return None
    orig_len, opt_len = len(original), len(optimized)
    orig_words = len(original.split())
    opt_words = len(optimized.split())
    pct = ((opt_len - orig_len) / orig_len * 100) if orig_len else 0
    return f"📈 Длина: {orig_len} → {opt_len} симв. ({pct:+.1f}%) | Слова: {orig_words} → {opt_words}"


def _rouge_scores(reference: str, candidate: str) -> tuple[float, float] | None:
    """Возвращает (R-1 F1, R-2 F1) или None при ошибке/пустых текстах."""
    if not reference.strip() or not candidate.strip():
        return None
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2"], use_stemmer=False)
        scores = scorer.score(reference, candidate)
        return scores["rouge1"].fmeasure, scores["rouge2"].fmeasure
    except Exception:
        return None


def _rouge_line(label: str, reference: str, candidate: str) -> str:
    """Строка ROUGE с подписью (исходный / предыдущий вариант) и интерпретацией."""
    scores = _rouge_scores(reference, candidate)
    if scores is None:
        return ""
    r1, r2 = scores
    if r1 >= 0.6:
        interp = "сохранён смысл и формулировки, аккуратное улучшение"
    elif r1 >= 0.35:
        interp = "умеренная переформулировка, добавлена структура"
    else:
        interp = "сильная переформулировка, новый вариант"
    return f"📊 {label}: R-1 {r1:.2f}, R-2 {r2:.2f} — {interp}"


def _count_structure_markers(text: str) -> int:
    """Число типичных структурных элементов промпта (роль, задача, формат и т.д.)."""
    if not text or not text.strip():
        return 0
    lower = text.lower()
    markers = [
        "ты —", "ты -", "твоя задача", "задача:", "формат:", "шаги:", "ограничения:",
        "ответь в формате", "выведи", "1.", "2.", "3.", "• ", "- ", "— "
    ]
    return sum(1 for m in markers if m in lower)


def _why_better_line(original: str, new_prompt: str, rouge_r1: float | None) -> str:
    """Одна фраза: почему новый вариант может быть лучше (эвристики)."""
    if not new_prompt.strip():
        return ""
    orig_len, new_len = len(original), len(new_prompt)
    orig_words, new_words = len(original.split()), len(new_prompt.split())
    struct_orig = _count_structure_markers(original)
    struct_new = _count_structure_markers(new_prompt)
    reasons = []
    if struct_new > struct_orig:
        reasons.append("добавлена структура (роль, задача, формат)")
    if new_len > orig_len * 1.2 and struct_new >= struct_orig:
        reasons.append("более развёрнутые инструкции")
    elif new_len < orig_len * 0.8 and (rouge_r1 is None or rouge_r1 >= 0.4):
        reasons.append("сжат без потери смысла")
    if rouge_r1 is not None and rouge_r1 >= 0.5:
        reasons.append("сохранены формулировки")
    if not reasons:
        reasons.append("переформулирован под лучшую работу с LLM")
    return "💡 Почему может быть лучше: " + ", ".join(reasons) + "."


async def _send_long_message(message: Message, text: str, parse_mode: str | None = None, reply_markup=None):
    """Отправляет текст одним или несколькими сообщениями, не превышая лимит Telegram."""
    if not text:
        return
    chunk_size = TELEGRAM_MAX_MESSAGE_LENGTH - 100
    if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return
    offset = 0
    parts = []
    while offset < len(text):
        chunk = text[offset : offset + chunk_size]
        if offset + chunk_size < len(text):
            chunk += "\n\n… (продолжение ниже)"
        parts.append(chunk)
        offset += chunk_size
    for i, part in enumerate(parts):
        mk = reply_markup if i == len(parts) - 1 else None
        await message.answer(part, parse_mode=parse_mode, reply_markup=mk)


def _is_llm_provider_error(exc: Exception) -> bool:
    """Проверяет, связана ли ошибка с недоступностью провайдера (403, регион и т.п.)."""
    name = type(exc).__name__
    msg = str(exc).lower()
    if name in ("PermissionDeniedError", "AuthenticationError"):
        return True
    if "403" in msg or "not available" in msg or "your region" in msg or "provider returned error" in msg:
        return True
    return False


def _format_preferences_for_prompt(user: dict) -> str:
    style = user.get("preference_style")
    goal = user.get("preference_goal")
    fmt = user.get("preference_format")
    if not style and not goal and not fmt:
        return ""
    parts = []
    if style:
        parts.append(f"Стиль ответов пользователя: {PREFERENCE_STYLE_LABELS.get(style, style)}.")
    if goal:
        goal_labels = [PREFERENCE_GOAL_LABELS.get(g.strip(), g) for g in goal.split(",") if g.strip()]
        if goal_labels:
            parts.append(f"Интересы/цели использования ИИ: {', '.join(goal_labels)}.")
    if fmt:
        parts.append(f"Предпочитаемый формат промптов: {PREFERENCE_FORMAT_LABELS.get(fmt, fmt)}.")
    if not parts:
        return ""
    return "Предпочтения пользователя (учитывай при улучшении промптов): " + " ".join(parts)


class SettingsStates(StatesGroup):
    editing_meta_prompt = State()
    editing_context = State()


class OnboardingStates(StatesGroup):
    selecting_goals = State()


class AgentStates(StatesGroup):
    answering_questions = State()


def _parse_goal_preference(value: str | None) -> list:
    if not value or not value.strip():
        return []
    return [g.strip() for g in value.split(",") if g.strip()]


@router.message(Command("start"))
async def cmd_start(
    message: Message, db_manager: SQLiteManager, state: FSMContext
):
    user_id = message.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    if not user.get("preference_style"):
        await state.clear()
        await message.answer(
            "👋 Привет! Я бот для улучшения и создания промптов к нейросетям (ChatGPT, Claude и др.). "
            "Я помогаю сделать запросы чёткими, структурированными и эффективными — чтобы модель лучше понимала задачу.\n\n"
            "Чтобы подстроиться под тебя, ответь на пару вопросов.\n\n"
            "Как тебе удобнее получать ответы?",
            reply_markup=get_preference_style_keyboard()
        )
        return
    if not user.get("preference_goal"):
        selected = _parse_goal_preference(user.get("preference_goal"))
        await state.set_state(OnboardingStates.selecting_goals)
        await state.update_data(selected_goals=selected)
        from bot.handlers.callbacks import GOAL_SELECT_TEXT
        await message.answer(
            GOAL_SELECT_TEXT,
            reply_markup=get_preference_goal_keyboard(selected)
        )
        return
    if not user.get("preference_format"):
        await message.answer(
            "Какой формат промптов тебе ближе?",
            reply_markup=get_preference_format_keyboard()
        )
        return

    await message.answer(
        "👋 Привет! Я бот для улучшения и создания промптов к нейросетям.\n\n"
        "Что я делаю: ты присылаешь сырой запрос или идею — я помогаю превратить его в чёткий, структурированный промпт, "
        "который нейросеть поймёт лучше. Можно получить один улучшенный вариант (простой режим) или вести диалог: "
        "я задам уточняющие вопросы и соберу промпт под твои цели.\n\n"
        "Просто отправь текст запроса. В /settings можно выбрать модель (DeepSeek, ChatGPT, Gemini и др.), "
        "режим работы и свои предпочтения.\n\n"
        "/settings — настройки | /help — справка",
        reply_markup=get_settings_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Справка:\n\n"
        "• Простой режим: отправь промпт — получишь улучшенный вариант (без памяти).\n"
        "• Режим агент: диалог с памятью, агент может задать уточняющие вопросы или предложить промпт.\n\n"
        "/settings — выбор LLM, режим, предпочтения, meta-промпт и контекст."
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, db_manager: SQLiteManager):
    user_id = message.from_user.id
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )

    from bot.handlers.callbacks import PROVIDER_NAMES, MODE_NAMES
    provider_name = PROVIDER_NAMES.get(user["llm_provider"], user["llm_provider"])
    mode_name = MODE_NAMES.get(user.get("mode", "simple"), "простой")

    await message.answer(
        f"⚙️ Настройки:\n\n"
        f"LLM: {provider_name} | Режим: {mode_name}\n\n"
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
async def handle_prompt(
    message: Message, db_manager: SQLiteManager, llm_service: LLMService, state: FSMContext
):
    user_id = message.from_user.id
    user_prompt = message.text
    user = await db_manager.get_or_create_user(
        user_id,
        DEFAULT_META_PROMPT,
        DEFAULT_CONTEXT
    )
    mode = user.get("mode", "simple")
    provider = user["llm_provider"] or "trinity"

    if mode == "agent":
        if await state.get_state() == AgentStates.answering_questions.state:
            await state.clear()
        processing_msg = await message.answer("🔄 Думаю...")
        try:
            history = await db_manager.get_agent_history(user_id)
            prefs_text = _format_preferences_for_prompt(user)
            system_prompt = (prefs_text + "\n\n" + AGENT_SYSTEM_PROMPT_BASE) if prefs_text else AGENT_SYSTEM_PROMPT_BASE
            focus_parts = [msg["content"][:200].strip() for msg in history if msg.get("role") == "user"][-2:]
            focus_str = "Ранее пользователь писал: " + " | ".join(focus_parts) if focus_parts else ""
            previous_agent_prompt = _get_previous_agent_prompt(history)
            if previous_agent_prompt:
                # Пользователь уточняет или правит уже сгенерированный ранее промпт
                user_content = (
                    "Вот текущий вариант промпта, который нужно улучшать и уточнять:\n"
                    f"{previous_agent_prompt}\n\n"
                    "Пользователь написал уточнения/правки ИМЕННО к этому промпту (это не новый независимый запрос):\n"
                    f"{user_prompt}\n\n"
                )
                if focus_str:
                    user_content += focus_str
            else:
                # Первый запрос или история была очищена — работаем как с новым промптом
                user_content = (focus_str + "\n\nТекущий запрос: " + user_prompt) if focus_str else user_prompt
            temperature = float(user.get("temperature", 0.4))
            reply = await llm_service.chat_with_history(
                user_content=user_content,
                history=history,
                system_prompt=system_prompt,
                provider=provider,
                temperature=temperature,
            )
            questions = _parse_agent_questions(reply)
            if questions:
                await processing_msg.delete()
                intro = reply.split(QUESTIONS_OPEN)[0].strip() if QUESTIONS_OPEN in reply else ""
                await state.set_state(AgentStates.answering_questions)
                await state.update_data(
                    agent_original_request=user_prompt,
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
                    await message.answer(
                        text,
                        parse_mode="HTML",
                        reply_markup=get_agent_question_single_keyboard(
                            i, q, answers, i == len(questions) - 1
                        ),
                    )
                return
            await db_manager.add_agent_message(user_id, "user", user_prompt)
            await db_manager.add_agent_message(user_id, "assistant", reply)
            await processing_msg.delete()
            try:
                formatted = _format_agent_reply_for_telegram(reply)
                _, prompt_block, _ = _parse_agent_reply(reply)
                if prompt_block.strip():
                    previous_agent_prompt = _get_previous_agent_prompt(history)
                    baseline = previous_agent_prompt if previous_agent_prompt else user_prompt
                    extra = []
                    metrics_line = _agent_metrics_line(baseline, prompt_block)
                    if metrics_line:
                        extra.append(metrics_line)
                    if previous_agent_prompt:
                        rouge_prev = _rouge_line("Предыдущий вариант → подправленный", previous_agent_prompt, prompt_block)
                        if rouge_prev:
                            extra.append(rouge_prev)
                        scores_prev = _rouge_scores(previous_agent_prompt, prompt_block)
                        rouge_r1 = scores_prev[0] if scores_prev else None
                        why_line = _why_better_line(previous_agent_prompt, prompt_block, rouge_r1)
                    else:
                        rouge_orig = _rouge_line("Похожесть на исходный запрос", user_prompt, prompt_block)
                        if rouge_orig:
                            extra.append(rouge_orig)
                        scores = _rouge_scores(user_prompt, prompt_block)
                        rouge_r1 = scores[0] if scores else None
                        why_line = _why_better_line(user_prompt, prompt_block, rouge_r1)
                    if why_line:
                        extra.append(why_line)
                    if extra:
                        formatted += "\n\n" + "\n".join(extra)
                await _send_long_message(
                    message,
                    formatted,
                    parse_mode="HTML",
                    reply_markup=get_agent_result_keyboard()
                )
            except Exception:
                await _send_long_message(
                    message,
                    reply[:TELEGRAM_MAX_MESSAGE_LENGTH - 50] + "\n\n… (сообщение обрезано)" if len(reply) > TELEGRAM_MAX_MESSAGE_LENGTH else reply,
                    reply_markup=get_agent_result_keyboard()
                )
        except Exception as e:
            error_code = type(e).__name__
            logger.error(f"Ошибка в режиме агента: {e}", exc_info=True)
            err_text_llm = (
                "❌ Сейчас не удаётся обратиться к модели <b>{pname}</b>.\n\n"
                "Часто это из‑за ограничений по региону или временной недоступности провайдера. "
                "Переключитесь на другую модель в настройках или нажмите кнопку ниже."
            )
            err_text_other = f"❌ Ошибка.\nКод: {error_code}\nПопробуйте позже."
            if _is_llm_provider_error(e):
                from bot.handlers.callbacks import PROVIDER_NAMES
                pname = PROVIDER_NAMES.get(provider, provider)
                text = err_text_llm.format(pname=pname)
                markup = get_llm_error_keyboard()
            else:
                text = err_text_other
                markup = None
            try:
                await processing_msg.edit_text(text, parse_mode="HTML" if markup else None, reply_markup=markup)
            except (TelegramBadRequest, Exception):
                await message.answer(text, parse_mode="HTML" if markup else None, reply_markup=markup)
        return

    processing_msg = await message.answer("🔄 Обрабатываю промпт...")

    try:
        meta_prompt = user["meta_prompt"] or DEFAULT_META_PROMPT
        context_prompt = user["context_prompt"] or DEFAULT_CONTEXT
        prefs_text = _format_preferences_for_prompt(user)
        if prefs_text:
            context_prompt = prefs_text + "\n\n" + context_prompt
        temperature = float(user.get("temperature", 0.4))

        optimized = await llm_service.optimize_prompt(
            user_prompt,
            meta_prompt,
            context_prompt,
            provider or "trinity",
            temperature=temperature,
        )

        original_length = len(user_prompt)
        optimized_length = len(optimized)
        original_words = len(user_prompt.split())
        optimized_words = len(optimized.split())

        await processing_msg.delete()

        escaped = _html_escape(optimized)
        header = "✨ <b>Оптимизированный промпт:</b> (нажми на блок, чтобы скопировать)"
        metrics = f"📈 Длина: {original_length} → {optimized_length} симв. ({((optimized_length - original_length) / original_length * 100):+.1f}%) | Слова: {original_words} → {optimized_words}"
        prompt_block = f"<blockquote><pre>{escaped}</pre></blockquote>"
        if len(escaped) <= 3500:
            await message.answer(
                f"{header}\n\n{prompt_block}\n\n{metrics}",
                parse_mode="HTML",
                reply_markup=get_result_nav_keyboard()
            )
        else:
            await message.answer(header, parse_mode="HTML")
            await message.answer(prompt_block, parse_mode="HTML")
            await message.answer(metrics, reply_markup=get_result_nav_keyboard())

    except ValueError as e:
        text = f"❌ Ошибка: {str(e)}\n\nПроверьте настройки в /settings"
        try:
            await processing_msg.edit_text(text)
        except (TelegramBadRequest, Exception):
            await message.answer(text)
    except Exception as e:
        error_code = type(e).__name__
        logger.error(f"Ошибка при обработке промпта: {e}", exc_info=True)
        if _is_llm_provider_error(e):
            from bot.handlers.callbacks import PROVIDER_NAMES
            pname = PROVIDER_NAMES.get(provider or "gemini", provider or "gemini")
            text = (
                f"❌ Сейчас не удаётся обратиться к модели <b>{pname}</b>.\n\n"
                f"Часто это из‑за ограничений по региону или временной недоступности провайдера. "
                f"Переключитесь на другую модель в настройках или нажмите кнопку ниже."
            )
            markup = get_llm_error_keyboard()
        else:
            text = (
                f"❌ Произошла ошибка при обработке промпта.\n\n"
                f"Код ошибки: {error_code}\n"
                f"Попробуйте повторить запрос позже."
            )
            markup = None
        try:
            await processing_msg.edit_text(text, parse_mode="HTML" if markup else None, reply_markup=markup)
        except (TelegramBadRequest, Exception):
            await message.answer(text, parse_mode="HTML" if markup else None, reply_markup=markup)

