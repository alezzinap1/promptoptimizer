import logging
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = {
    "deepseek": "deepseek/deepseek-chat",
    "openai": "openai/gpt-4o-mini",
    "gemini": "google/gemini-2.5-flash-lite",
    "grok": "x-ai/grok-4-fast",
    "nemo": "mistralai/mistral-nemo",
    "mimo": "xiaomi/mimo-v2-flash",
    "trinity": "arcee-ai/trinity-large-preview:free",
    "gpt5nano": "openai/gpt-5-nano",
    "deepseek_r1t": "tngtech/deepseek-r1t-chimera:free",
    "qwen3": "qwen/qwen3-235b-a22b-2507",
}


class LLMService:
    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None

    def initialize(self, openrouter_api_key: str):
        self.client = AsyncOpenAI(
            api_key=openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
        )

    def _get_model_id(self, provider: str) -> str:
        return OPENROUTER_MODELS.get(provider) or OPENROUTER_MODELS["trinity"]

    async def optimize_prompt(
        self,
        user_prompt: str,
        meta_prompt: str,
        context_prompt: Optional[str] = None,
        provider: str = "trinity",
        temperature: float = 0.4,
    ) -> str:
        if not self.client:
            raise ValueError("LLM сервис не инициализирован")
        model = self._get_model_id(provider)
        full_prompt = f"{meta_prompt}\n\nПромпт для оптимизации:\n{user_prompt}"
        messages = []
        if context_prompt:
            messages.append({"role": "system", "content": context_prompt})
        messages.append({"role": "user", "content": full_prompt})
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            raise Exception("Пустой ответ от OpenRouter")
        except Exception as e:
            logger.error(f"Ошибка OpenRouter: {e}")
            raise

    async def chat_with_history(
        self,
        user_content: str,
        history: List[Dict[str, str]],
        system_prompt: str,
        provider: str = "trinity",
        temperature: float = 0.4,
    ) -> str:
        if not self.client:
            raise ValueError("LLM сервис не инициализирован")
        model = self._get_model_id(provider)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_content})
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            raise Exception("Пустой ответ от OpenRouter")
        except Exception as e:
            logger.error(f"Ошибка OpenRouter: {e}")
            raise
