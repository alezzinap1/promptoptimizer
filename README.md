# Meta-Prompt Optimizer Bot

Telegram-бот для улучшения и создания промптов для LLM. Два режима: **простой** (улучшение за один запрос) и **агент** (диалог с памятью, уточняющие вопросы с кнопками). LLM через [OpenRouter](https://openrouter.ai): DeepSeek, ChatGPT, Gemini, Grok 4 Fast, Mistral Nemo, Xiaomi Mimo V2 Flash.

## Возможности

- **Простой режим** — отправь промпт, получи улучшенный вариант в блоке цитаты и моноширины (копирование по нажатию), метрики длины и слов.
- **Режим агента** — диалог с памятью (последние 16 сообщений); агент оценивает сложность запроса и либо сразу даёт промпт, либо задаёт 1–5 уточняющих вопросов с кнопками выбора; после ответов формирует промпт. Кнопка **«Принять промпт»** обнуляет историю и отделяет сессию.
- **Предпочтения** — при первом входе бот задаёт 3 вопроса (стиль ответов, цели использования ИИ до 4 вариантов, формат промптов); предпочтения хранятся в БД; их можно изменить в настройках → Кастомизация.
- **Выбор LLM** — DeepSeek, ChatGPT, Gemini, Grok 4 Fast (xAI), Mistral Nemo, Xiaomi Mimo V2 Flash через один API OpenRouter.
- **Кастомизация** — в настройках отдельная кнопка: предпочтения, meta-промпт, контекст и **температура** (влияет на стабильность и разнообразие ответов модели).
- **Метрики в агенте** — длина и слова (исходный vs последний вариант), ROUGE (похожесть), краткое объяснение «почему может быть лучше».

## Пример работы
1) Старт (при первом запуске агент так же уточнит предпочтения пользователя, которые будут учитываться при формировании контекстного окна) <img width="570" height="332" alt="image" src="https://github.com/user-attachments/assets/fafe3cab-fa47-4a1b-a9ef-3fcd7b635c88" />

2) Выбор LLM <img width="339" height="385" alt="image" src="https://github.com/user-attachments/assets/26406629-18ea-45bf-b381-3200e8d935e9" />

3) Выбор режима - простой enhancer и agent mode <img width="556" height="311" alt="image" src="https://github.com/user-attachments/assets/adc40f73-3bd2-4def-bb0c-03ab1ce09642" />

4) Найтройки кастомизации <img width="555" height="317" alt="image" src="https://github.com/user-attachments/assets/2f8a8069-2a46-4285-9b86-1946a0f73e80" />

5) Формируем промпт на скорую руку, отправляем боту в режиме агента. <img width="556" height="412" alt="image" src="https://github.com/user-attachments/assets/a9c93af3-e02b-4712-a4fe-798b0c96f42f" />

6) Так как очевидно то, что мы написали весьма расплывчато, агент оценил сложонсть и выставил нам вопросы (количество зависит так же от сложности). <img width="396" height="723" alt="image" src="https://github.com/user-attachments/assets/c9012dfb-b34b-4cea-a8e5-3ad7ab203fa2" /> <img width="438" height="541" alt="image" src="https://github.com/user-attachments/assets/aa44d251-d480-46b6-8205-ec62cd328079" />

7) Выбираем ответы и жмем готово <img width="346" height="57" alt="image" src="https://github.com/user-attachments/assets/f8aad45f-2cef-4d87-878c-3b153c85cce7" />

8) Ответ агента в данном случае такой <img width="1133" height="893" alt="image" src="https://github.com/user-attachments/assets/df3d251b-ac26-4e2f-8b1f-3d4ea461f065" />

9) Дальше можно обсудить этот промпт с агентом и уточнить детали.


## Технический стек

- Python 3.10+
- aiogram 3.x
- OpenRouter API (один ключ для всех моделей)
- SQLite (настройки пользователей, температура, история агента)
- rouge-score (метрики для агента)

## Установка

1. Клонируйте репозиторий.

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте `.env` (по образцу `env_example.txt`):
   - **TELEGRAM_BOT_TOKEN** — токен от [@BotFather](https://t.me/BotFather)
   - **OPENROUTER_API_KEY** — ключ с [OpenRouter](https://openrouter.ai/keys)

## Запуск

Локально:
```bash
python -m bot.main
```

Docker (Linux-сервер):
```bash
docker build -t prompt-optimizer-bot .
docker run -d --restart unless-stopped --env-file .env -e DB_PATH=/app/data/bot.db -v prompt_bot_data:/app/data prompt-optimizer-bot
```
Создайте `.env` по образцу `env_example.txt` с `TELEGRAM_BOT_TOKEN` и `OPENROUTER_API_KEY`. База SQLite сохраняется в volume `prompt_bot_data` (в контейнере: `/app/data/bot.db`).

## Использование

1. `/start` — при первом входе 3 вопроса о предпочтениях, затем приветствие.
2. Отправь промпт: в **простом** режиме — улучшенный промпт в блоке и метрики; в **режиме агента** — ответ с учётом истории, возможно уточняющие вопросы с кнопками, затем промпт с метриками и ROUGE; кнопка «Принять промпт» завершает сессию.
3. `/settings` — LLM, режим, **Кастомизация** (предпочтения, meta-промпт, контекст, температура).

## Команды

- `/start` — приветствие
- `/help` — справка
- `/settings` — настройки (LLM, режим, кастомизация)

## Особенности

- Один API OpenRouter для нескольких моделей.
- Предпочтения и температура хранятся в БД и используются при вызовах LLM.
- В режиме агента хранятся последние 16 сообщений диалога (скользящее окно).
- Улучшенный промпт выводится в блоке цитаты и моноширины (копирование по нажатию в Telegram).
