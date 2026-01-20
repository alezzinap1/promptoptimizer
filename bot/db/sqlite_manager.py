import sqlite3
import aiosqlite
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SQLiteManager:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    llm_provider TEXT DEFAULT 'gemini',
                    meta_prompt TEXT,
                    context_prompt TEXT,
                    ab_testing_enabled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("База данных инициализирована")

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def create_user(
        self,
        user_id: int,
        meta_prompt: str,
        context_prompt: str,
        llm_provider: str = "gemini"
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, llm_provider, meta_prompt, context_prompt)
                VALUES (?, ?, ?, ?)
            """, (user_id, llm_provider, meta_prompt, context_prompt))
            await db.commit()
            logger.info(f"Создан пользователь {user_id}")

    async def update_user_setting(self, user_id: int, field: str, value: Any):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE users SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (value, user_id)
            )
            await db.commit()
            logger.info(f"Обновлена настройка {field} для пользователя {user_id}")

    async def get_or_create_user(
        self,
        user_id: int,
        default_meta_prompt: str,
        default_context_prompt: str
    ) -> Dict[str, Any]:
        user = await self.get_user(user_id)
        if user is None:
            await self.create_user(
                user_id,
                default_meta_prompt,
                default_context_prompt
            )
            user = await self.get_user(user_id)
        return user


