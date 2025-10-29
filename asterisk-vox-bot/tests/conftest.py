import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if "aiofiles" not in sys.modules:
    aiofiles = types.ModuleType("aiofiles")

    class _AsyncFile:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def write(self, data):
            return len(data)

        async def read(self):
            return b""

    def open(*args, **kwargs):
        return _AsyncFile()

    aiofiles.open = open  # type: ignore[attr-defined]
    sys.modules["aiofiles"] = aiofiles


if "aiohttp" not in sys.modules:
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    class _DummyResponse:
        status = 200

        async def text(self):
            return ""

        async def json(self):
            return {}

        @property
        def content(self):
            class _Content:
                async def iter_chunked(self, size):
                    if False:
                        yield b""

            return _Content()

    class _ResponseContext:
        async def __aenter__(self):
            return _DummyResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class ClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return _ResponseContext()

    aiohttp.ClientSession = ClientSession  # type: ignore[attr-defined]
    aiohttp.ClientTimeout = ClientTimeout  # type: ignore[attr-defined]
    aiohttp.ClientError = ClientError  # type: ignore[attr-defined]
    sys.modules["aiohttp"] = aiohttp
