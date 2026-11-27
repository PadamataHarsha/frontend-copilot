import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class LLMConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: float
    max_output_tokens: int

    @property
    def llm_max_output_tokens(self) -> int:
        return self.max_output_tokens

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY is not configured")

        try:
            timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
            max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "700"))
        except ValueError as error:
            raise LLMConfigurationError("LLM settings are invalid") from error

        if timeout_seconds <= 0 or max_output_tokens <= 0:
            raise LLMConfigurationError("LLM settings are invalid")

        return cls(
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            model=os.getenv("LLM_MODEL", "qwen/qwen3.8-27b"),
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_output_tokens=min(max_output_tokens, 700),
        )


def get_settings() -> LLMConfig:
    return LLMConfig.from_env()