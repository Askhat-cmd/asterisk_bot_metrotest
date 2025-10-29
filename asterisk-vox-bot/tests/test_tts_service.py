import asyncio
from pathlib import Path

import pytest

from app.backend.services import tts_service as tts_module


@pytest.fixture
def prepared_tts_service(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TTS_AUDIO_DIR", str(tmp_path / "audio"))

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    asterisk_dir = tmp_path / "asterisk"
    asterisk_dir.mkdir()

    original_makedirs = tts_module.os.makedirs

    def fake_makedirs(path, exist_ok=True):
        if path == "/var/lib/asterisk/sounds/ru":
            path = str(asterisk_dir)
        return original_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(tts_module.os, "makedirs", fake_makedirs)

    service = tts_module.TTSService()
    service.asterisk_sounds_dir = str(asterisk_dir)
    return service


def test_text_to_speech_returns_existing_file(prepared_tts_service):
    dest = Path(prepared_tts_service.asterisk_sounds_dir) / "sample.wav"
    dest.write_bytes(b"fake")

    async def run():
        result = await prepared_tts_service.text_to_speech("hello", filename="sample")
        assert result == "sample"

    asyncio.run(run())


def test_text_to_speech_rejects_empty_text(prepared_tts_service):
    async def run():
        with pytest.raises(ValueError):
            await prepared_tts_service.text_to_speech("   ")

    asyncio.run(run())
