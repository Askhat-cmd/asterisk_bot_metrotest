import asyncio
import sys
import types

from app.backend.services import asr_service as asr_module


class DummyYandexASR:
    def __init__(self):
        self.calls = []

    async def speech_to_text(self, audio_path, prompt=None):
        self.calls.append((audio_path, prompt))
        return "recognized"


def test_asr_service_delegates_to_yandex(monkeypatch):
    dummy = DummyYandexASR()

    dummy_module = types.SimpleNamespace(get_yandex_asr_service=lambda: dummy)
    monkeypatch.setitem(sys.modules, "app.backend.services.yandex_asr_service", dummy_module)
    monkeypatch.setattr(asr_module, "asr_service", None)

    async def run():
        service = asr_module.ASRService()
        result = await service.speech_to_text("audio.wav", prompt="hint")

        assert result == "recognized"
        assert dummy.calls == [("audio.wav", "hint")]

    asyncio.run(run())


def test_get_asr_service_returns_singleton(monkeypatch):
    dummy = object()

    def fake_constructor():
        return dummy

    monkeypatch.setattr(asr_module, "ASRService", fake_constructor)
    monkeypatch.setattr(asr_module, "asr_service", None)

    first = asr_module.get_asr_service()
    second = asr_module.get_asr_service()

    assert first is dummy
    assert second is dummy
