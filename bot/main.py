import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.db.sqlite_manager import SQLiteManager
from bot.services.llm_client import LLMService
from bot.handlers import commands_router, callbacks_router
from bot.handlers.commands import DEFAULT_META_PROMPT, DEFAULT_CONTEXT

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    if not gemini_api_key and not deepseek_api_key:
        raise ValueError("Необходимо указать хотя бы один API ключ (GEMINI_API_KEY или DEEPSEEK_API_KEY)")

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    db_manager = SQLiteManager()
    await db_manager.init_db()

    llm_service = LLMService()
    llm_service.initialize(
        gemini_api_key=gemini_api_key,
        deepseek_api_key=deepseek_api_key
    )

    async def inject_dependencies(handler, event, data):
        data["db_manager"] = db_manager
        data["llm_service"] = llm_service
        return await handler(event, data)

    dp.message.middleware.register(inject_dependencies)
    dp.callback_query.middleware.register(inject_dependencies)

    dp.include_router(commands_router)
    dp.include_router(callbacks_router)

    logger.info("Бот запущен")
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)

