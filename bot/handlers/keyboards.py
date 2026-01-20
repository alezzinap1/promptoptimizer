from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Выбрать LLM", callback_data="settings_llm"),
            InlineKeyboardButton(text="🧪 A/B тестирование", callback_data="settings_ab")
        ],
        [
            InlineKeyboardButton(text="✏️ Редактировать meta-промпт", callback_data="settings_meta")
        ],
        [
            InlineKeyboardButton(text="📝 Редактировать контекст", callback_data="settings_context")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_llm_keyboard(current_provider: str) -> InlineKeyboardMarkup:
    gemini_text = "✅ Gemini" if current_provider == "gemini" else "Gemini"
    deepseek_text = "✅ DeepSeek" if current_provider == "deepseek" else "DeepSeek"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=gemini_text, callback_data="llm_gemini")
        ],
        [
            InlineKeyboardButton(text=deepseek_text, callback_data="llm_deepseek")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_ab_test_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выбрать вариант A", callback_data="ab_select_a"),
            InlineKeyboardButton(text="✅ Выбрать вариант B", callback_data="ab_select_b")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_ab_toggle_keyboard(ab_enabled: bool) -> InlineKeyboardMarkup:
    status_text = "✅ Включено" if ab_enabled else "❌ Выключено"
    toggle_text = "❌ Выключить" if ab_enabled else "✅ Включить"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{status_text} → {toggle_text}", callback_data="ab_toggle")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_cancel_edit_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_edit")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


