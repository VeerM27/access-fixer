import pytest
from google.adk.models import Gemini, LlmRequest, LlmResponse
from google.genai import errors

from access_fixer.fix.fixer import FallbackGemini


def _fake_gemini(failing_code: int):
    async def generate(self, llm_request, stream=False):
        if llm_request.model == "main-model":
            raise errors.APIError(failing_code, {"error": {"message": "nope"}}, None)
        yield LlmResponse(model_version=llm_request.model)

    return generate


async def _models_used(model: FallbackGemini) -> list[str]:
    request = LlmRequest(model="main-model")
    return [r.model_version async for r in model.generate_content_async(request)]


@pytest.mark.parametrize("code", [429, 503])
async def test_switches_to_fallback_model(monkeypatch, code):
    monkeypatch.setattr(Gemini, "generate_content_async", _fake_gemini(code))
    model = FallbackGemini(model="main-model", fallback_model="backup-model")
    assert await _models_used(model) == ["backup-model"]


async def test_other_errors_are_not_hidden(monkeypatch):
    monkeypatch.setattr(Gemini, "generate_content_async", _fake_gemini(400))
    model = FallbackGemini(model="main-model", fallback_model="backup-model")
    with pytest.raises(errors.APIError):
        await _models_used(model)
