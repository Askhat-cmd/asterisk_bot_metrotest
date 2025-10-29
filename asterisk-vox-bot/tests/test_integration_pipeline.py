import asyncio

from app.backend.services.simple_vad_service import SimpleVADService


class DummyASR:
    def __init__(self):
        self.calls = []

    async def speech_to_text(self, audio_path, prompt=None):
        self.calls.append((audio_path, prompt))
        return "recognized text"


class DummyTTS:
    def __init__(self):
        self.calls = []

    async def text_to_speech(self, text, filename=None):
        self.calls.append((text, filename))
        return f"audio-for-{filename or 'auto'}"


def test_asr_vad_tts_pipeline():
    asr = DummyASR()
    tts = DummyTTS()
    events = []
    finished = asyncio.Event()

    async def run_pipeline():
        vad = SimpleVADService(
            silence_timeout=0.1,
            min_recording_time=0.0,
            max_recording_time=0.5,
            debug_logging=False,
        )

        async def on_finish(channel_id, recording_id, reason):
            text = await asr.speech_to_text(recording_id)
            audio = await tts.text_to_speech(text, filename=recording_id)
            events.append((channel_id, text, audio, reason))
            finished.set()

        await vad.start_monitoring("channel-1", "record-1", on_finish)
        await vad.update_activity("channel-1")
        await asyncio.sleep(0.25)

        await finished.wait()
        await asyncio.sleep(0.05)

        assert events == [("channel-1", "recognized text", "audio-for-record-1", "silence_detected")]
        assert not vad.is_monitoring("channel-1")
        assert asr.calls == [("record-1", None)]
        assert tts.calls == [("recognized text", "record-1")]

    asyncio.run(run_pipeline())
