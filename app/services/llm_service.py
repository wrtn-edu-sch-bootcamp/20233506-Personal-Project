import asyncio
import json
import logging
import re

from openai import AsyncOpenAI, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

MAX_RETRIES_PER_KEY = 1
RETRY_DELAY = 3


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()

        if settings.llm_provider == "gemini":
            self._keys = settings.get_gemini_keys()
            if not self._keys:
                raise ValueError("No Gemini API keys configured")
            self._key_idx = 0
            self._clients = [
                AsyncOpenAI(api_key=k, base_url=GEMINI_BASE_URL)
                for k in self._keys
            ]
            self._model = settings.gemini_model
            logger.info("LLM: model=%s, %d API keys loaded", self._model, len(self._keys))
        else:
            self._keys = [settings.openai_api_key]
            self._clients = [AsyncOpenAI(api_key=settings.openai_api_key)]
            self._key_idx = 0
            self._model = settings.openai_model
            logger.info("LLM: model=%s (OpenAI)", self._model)

    def _next_client(self) -> AsyncOpenAI:
        self._key_idx = (self._key_idx + 1) % len(self._clients)
        return self._clients[self._key_idx]

    @property
    def _client(self) -> AsyncOpenAI:
        return self._clients[self._key_idx]

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> str:
        kwargs: dict = {
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format:
            kwargs["response_format"] = response_format

        tried = 0
        total_keys = len(self._clients)

        while tried < total_keys:
            client = self._client
            for attempt in range(MAX_RETRIES_PER_KEY):
                try:
                    response = await client.chat.completions.create(
                        model=self._model, **kwargs,
                    )
                    return (response.choices[0].message.content or "").strip()
                except RateLimitError:
                    if attempt < MAX_RETRIES_PER_KEY - 1:
                        await asyncio.sleep(RETRY_DELAY)

            key_hint = self._keys[self._key_idx][:10]
            logger.warning("Key %s... rate limited, rotating", key_hint)
            self._next_client()
            tried += 1

        raise RateLimitError(
            message=f"All {total_keys} API keys exhausted",
            response=None,  # type: ignore[arg-type]
            body=None,
        )

    async def extract_from_image(self, image_b64: str, mime_type: str = "image/jpeg") -> str:
        tried = 0
        total_keys = len(self._clients)

        while tried < total_keys:
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": "이 이미지는 등기부등본입니다. 이미지에 있는 모든 텍스트를 그대로 추출하여 반환하세요."},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                            {"type": "text", "text": "이 등기부등본 이미지의 모든 텍스트를 추출해주세요."},
                        ]},
                    ],
                )
                return (response.choices[0].message.content or "").strip()
            except RateLimitError:
                logger.warning("Image extraction rate limited, rotating key")
                self._next_client()
                tried += 1
        return ""

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> dict:
        raw = await self.chat(
            system_prompt,
            user_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = _extract_json(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON: %s", raw[:300])
            return {}


def _extract_json(text: str) -> str:
    """Strip markdown code fences if the model wraps JSON in them."""
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def get_llm_service() -> LLMService:
    return LLMService()
