import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import google.generativeai as genai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        pass


class GeminiClient(LLMClient):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model_name = 'gemini-1.5-flash'

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        try:
            model = genai.GenerativeModel(self.model_name)
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
            )

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )
            )

            if response.text:
                return response.text.strip()
            else:
                raise Exception("Пустой ответ от Gemini API")
        except Exception as e:
            logger.error(f"Ошибка Gemini API: {e}")
            raise


class DeepSeekClient(LLMClient):

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            else:
                raise Exception("Пустой ответ от DeepSeek API")
        except Exception as e:
            logger.error(f"Ошибка DeepSeek API: {e}")
            raise


class LLMService:
    def __init__(self):
        self.gemini_client: Optional[GeminiClient] = None
        self.deepseek_client: Optional[DeepSeekClient] = None

    def initialize(self, gemini_api_key: Optional[str] = None, deepseek_api_key: Optional[str] = None):
        if gemini_api_key:
            self.gemini_client = GeminiClient(gemini_api_key)
        if deepseek_api_key:
            self.deepseek_client = DeepSeekClient(deepseek_api_key)

    async def optimize_prompt(
        self,
        user_prompt: str,
        meta_prompt: str,
        context_prompt: Optional[str] = None,
        provider: str = "gemini",
        temperature: float = 0.7
    ) -> str:
        client = self._get_client(provider)
        if not client:
            raise ValueError(f"Провайдер {provider} не инициализирован")

        full_prompt = f"{meta_prompt}\n\nПромпт для оптимизации:\n{user_prompt}"

        result = await client.generate(
            prompt=full_prompt,
            temperature=temperature,
            system_prompt=context_prompt
        )

        return result

    def _get_client(self, provider: str) -> Optional[LLMClient]:
        if provider == "gemini":
            return self.gemini_client
        elif provider == "deepseek":
            return self.deepseek_client
        else:
            return None

