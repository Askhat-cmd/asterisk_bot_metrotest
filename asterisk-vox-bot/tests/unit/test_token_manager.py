from datetime import datetime, timedelta
import types
import importlib.util
import sys
from pathlib import Path

# Подключаем ready_solution.py как модуль
mod_path = Path(__file__).resolve().parents[2] / "ready_solution.py"
spec = importlib.util.spec_from_file_location("ready_solution", str(mod_path))
ready_solution = importlib.util.module_from_spec(spec)
sys.modules["ready_solution"] = ready_solution
spec.loader.exec_module(ready_solution)

YandexTokenManager = ready_solution.YandexTokenManager

def test_token_needs_refresh_when_missing_token():
    m = YandexTokenManager("fake", "folder")
    m.iam_token = None
    m.token_expires_at = None
    assert m.token_needs_refresh() is True

def test_token_needs_refresh_when_expired():
    m = YandexTokenManager("fake", "folder")
    m.iam_token = "abc"
    m.token_expires_at = datetime.now() - timedelta(minutes=1)
    assert m.token_needs_refresh() is True

def test_token_needs_refresh_when_valid():
    m = YandexTokenManager("fake", "folder")
    m.iam_token = "abc"
    # больше чем 30 минут до истечения
    m.token_expires_at = datetime.now() + timedelta(hours=1)
    assert m.token_needs_refresh() is False

def test_token_needs_refresh_within_30min():
    m = YandexTokenManager("fake", "folder")
    m.iam_token = "abc"
    # осталось меньше 30 минут — должен обновляться
    m.token_expires_at = datetime.now() + timedelta(minutes=10)
    assert m.token_needs_refresh() is True
