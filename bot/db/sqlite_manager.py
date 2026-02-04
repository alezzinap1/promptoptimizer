import aiosqlite
from typing import Optional, Dict, Any, List
import logging
import sqlite3

logger = logging.getLogger(__name__)

AGENT_HISTORY_LIMIT = 16


class SQLiteManager:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    llm_provider TEXT DEFAULT 'trinity',
                    meta_prompt TEXT,
                    context_prompt TEXT,
                    ab_testing_enabled INTEGER DEFAULT 0,
                    mode TEXT DEFAULT 'simple',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                await db.execute("ALTER TABLE users ADD COLUMN mode TEXT DEFAULT 'simple'")
                await db.commit()
            except aiosqlite.OperationalError:
                await db.rollback()
            for col in ("preference_style", "preference_goal", "preference_format"):
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
                    await db.commit()
                except aiosqlite.OperationalError:
                    await db.rollback()
            try:
                await db.execute("ALTER TABLE users ADD COLUMN temperature REAL DEFAULT 0.4")
                await db.commit()
            except aiosqlite.OperationalError:
                await db.rollback()
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_conversation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    d = dict(row)
                    if "mode" not in d:
                        d["mode"] = "simple"
                    if "temperature" not in d or d["temperature"] is None:
                        d["temperature"] = 0.4
                    return d
                return None

    async def create_user(
        self,
        user_id: int,
        meta_prompt: str,
        context_prompt: str,
        llm_provider: str = "trinity",
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
            try:
                await self.create_user(
                    user_id,
                    default_meta_prompt,
                    default_context_prompt
                )
            except sqlite3.IntegrityError:
                pass
            user = await self.get_user(user_id)
        if user is None:
            raise RuntimeError("get_or_create_user: user still None after create")
        if "mode" not in user:
            user["mode"] = "simple"
        return user

    async def add_agent_message(self, user_id: int, role: str, content: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO agent_conversation (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
            await db.commit()
            async with db.execute(
                "SELECT COUNT(*) FROM agent_conversation WHERE user_id = ?",
                (user_id,)
            ) as cur:
                n = (await cur.fetchone())[0]
            if n > AGENT_HISTORY_LIMIT:
                await db.execute(
                    """DELETE FROM agent_conversation WHERE user_id = ? AND id IN (
                        SELECT id FROM agent_conversation WHERE user_id = ? ORDER BY id ASC LIMIT ?
                    )""",
                    (user_id, user_id, n - AGENT_HISTORY_LIMIT)
                )
                await db.commit()

    async def get_agent_history(self, user_id: int, limit: int = AGENT_HISTORY_LIMIT) -> List[Dict[str, str]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT role, content FROM agent_conversation
                   WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        out = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        return out

    async def clear_agent_history(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM agent_conversation WHERE user_id = ?", (user_id,))
            await db.commit()