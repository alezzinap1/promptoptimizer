from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 LLM", callback_data="settings_llm"),
            InlineKeyboardButton(text="🔄 Режим", callback_data="settings_mode"),
            InlineKeyboardButton(text="⚙️ Кастомизация", callback_data="settings_customization")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_customization_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Предпочтения", callback_data="settings_preferences")],
        [
            InlineKeyboardButton(text="✏️ Meta-промпт", callback_data="settings_meta"),
            InlineKeyboardButton(text="📝 Контекст", callback_data="settings_context")
        ],
        [InlineKeyboardButton(text="🌡 Температура", callback_data="settings_temperature")],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_temperature_keyboard(current: float) -> InlineKeyboardMarkup:
    options = (0.1, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9)
    row = []
    for t in options:
        label = f"{'✅ ' if abs(current - t) < 0.01 else ''}{t}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"temp_{t}"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        row,
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="customization_back"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_llm_keyboard(current_provider: str) -> InlineKeyboardMarkup:
    providers = (
        "deepseek",
        "openai",
        "gemini",
        "grok",
        "nemo",
        "mimo",
        "trinity",
        "gpt5nano",
        "deepseek_r1t",
        "qwen3",
    )
    labels = {
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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current_provider == p else ''}{labels[p]}",
                callback_data=f"llm_{p}"
            )
        ]
        for p in providers
    ] + [
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    simple_text = "✅ Простой" if current_mode == "simple" else "Простой"
    agent_text = "✅ Агент" if current_mode == "agent" else "Агент"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=simple_text, callback_data="mode_simple"),
            InlineKeyboardButton(text=agent_text, callback_data="mode_agent")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_llm_error_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под сообщением об ошибке LLM: переключиться на стабильную модель (Gemini)."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Переключиться на Gemini (доступен в РФ)", callback_data="llm_gemini")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="nav_settings")],
    ])
    return keyboard


def get_result_nav_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под результатом: переход отправляет новое сообщение, результат остаётся в истории."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="nav_settings")
        ]
    ])
    return keyboard


def get_agent_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под ответом агента с промптом: принять промпт (обнулить историю) + навигация."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять промпт", callback_data="agent_accept_prompt")],
        [InlineKeyboardButton(text="💬 Уточнить ещё", callback_data="agent_continue")],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="nav_settings")
        ]
    ])
    return keyboard


def get_agent_questions_keyboard(questions: list, answers: dict) -> InlineKeyboardMarkup:
    """Клавиатура для ответов на уточняющие вопросы агента. Варианты — столбиком."""
    rows = []
    for q_idx, q in enumerate(questions):
        opts = q.get("options") or []
        for opt_idx, opt in enumerate(opts):
            label = (opt[:37] + "…") if len(opt) > 40 else opt
            selected = answers.get(q_idx)
            if isinstance(selected, list):
                is_selected = opt_idx in selected
            else:
                is_selected = selected == opt_idx
            if is_selected:
                label = "✅ " + label
            rows.append([InlineKeyboardButton(text=label, callback_data=f"aq_{q_idx}_{opt_idx}")])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="aq_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_agent_question_single_keyboard(
    q_idx: int, question: dict, answers: dict, is_last: bool
) -> InlineKeyboardMarkup:
    """Клавиатура под одним вопросом: варианты ответа столбиком, при is_last — кнопка «Готово»."""
    opts = question.get("options") or []
    rows = []
    for opt_idx, opt in enumerate(opts):
        label = (opt[:37] + "…") if len(opt) > 40 else opt
        selected = answers.get(q_idx)
        if isinstance(selected, list):
            is_selected = opt_idx in selected
        else:
            is_selected = selected == opt_idx
        if is_selected:
            label = "✅ " + label
        rows.append([InlineKeyboardButton(text=label, callback_data=f"aq_{q_idx}_{opt_idx}")])
    if is_last:
        rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="aq_done")])
    # Пользователь может в любой момент пропустить вопросы и сразу получить промпт
    rows.append([InlineKeyboardButton(text="⚡ Сразу дать промпт (без вопросов)", callback_data="aq_skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_preference_style_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Точные, по делу", callback_data="pref_style_precise"),
            InlineKeyboardButton(text="Сбалансированные", callback_data="pref_style_balanced")
        ],
        [
            InlineKeyboardButton(text="Развёрнутые с примерами", callback_data="pref_style_creative")
        ]
    ])
    return keyboard


GOAL_OPTIONS = [
    ("code", "Код и техника"),
    ("study", "Учёба и образование"),
    ("creative", "Тексты и креатив"),
    ("analysis", "Анализ данных"),
    ("work", "Работа и бизнес"),
    ("research", "Исследования"),
    ("writing", "Письмо и редактура"),
    ("hobby", "Хобби и развлечения"),
    ("learning", "Самообразование"),
    ("other", "Разное"),
]


def get_preference_goal_keyboard(selected: list) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for goal_id, label in GOAL_OPTIONS:
        prefix = "✅ " if goal_id in selected else ""
        row.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"pref_goal_toggle_{goal_id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="pref_goal_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_preference_format_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Короткие и чёткие", callback_data="pref_format_short"),
            InlineKeyboardButton(text="Структурированные", callback_data="pref_format_structured")
        ],
        [
            InlineKeyboardButton(text="Подробные с инструкциями", callback_data="pref_format_detailed")
        ]
    ])
    return keyboard


def get_cancel_edit_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_edit"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
        ]
    ])
    return keyboard


