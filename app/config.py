from __future__ import annotations

import os
import sys
from getpass import getpass
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PLACEHOLDER_TOKEN = "123456789:REPLACE_WITH_YOUR_REAL_TOKEN"


def load_env(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from .env without an extra dependency."""
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path
    log_level: str = "INFO"
    admin_ids: tuple[int, ...] = ()
    audd_api_token: str = ""


def get_settings() -> Settings:
    load_env()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or is_placeholder_token(token):
        if not sys.stdin.isatty():
            raise RuntimeError(
                "BOT_TOKEN sozlanmagan. Railway dashboard ichida "
                "Variables -> BOT_TOKEN qiymatini BotFather tokeni bilan kiriting."
            )
        token = ask_and_save_token()

    db_path = Path(os.getenv("DATABASE_PATH", "data/musiqa_bot.sqlite3"))
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path

    return Settings(
        bot_token=token,
        database_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        audd_api_token=os.getenv("AUDD_API_TOKEN", "").strip(),
    )


def is_placeholder_token(token: str) -> bool:
    return token.strip() == PLACEHOLDER_TOKEN


def parse_admin_ids(raw_value: str) -> tuple[int, ...]:
    admin_ids: list[int] = []
    for item in raw_value.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            admin_ids.append(int(item))
        except ValueError:
            print(f"ADMIN_IDS ichida noto'g'ri ID bor, o'tkazib yuborildi: {item}")
    return tuple(admin_ids)


def ask_and_save_token() -> str:
    print("BOT_TOKEN topilmadi.")
    print("BotFather'dan olgan YANGI tokeningizni kiriting.")
    print("Eslatma: chatga yuborilgan eski tokenni BotFather orqali almashtiring.")
    try:
        token = getpass("BOT_TOKEN: ").strip()
    except Exception:
        token = input("BOT_TOKEN: ").strip()

    if not token:
        raise RuntimeError("Token kiritilmadi. Bot ishga tushmadi.")

    save_env_value("BOT_TOKEN", token)
    os.environ["BOT_TOKEN"] = token
    print(".env faylga BOT_TOKEN saqlandi. Keyingi safar faqat python main.py yetadi.")
    return token


def save_env_value(key: str, value: str) -> None:
    env_path = ROOT_DIR / ".env"
    lines: list[str] = []
    found = False

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)

    if not found:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(f"{key}={value}")

    if not any(line.strip().startswith("DATABASE_PATH=") for line in updated):
        updated.append("DATABASE_PATH=data/musiqa_bot.sqlite3")
    if not any(line.strip().startswith("LOG_LEVEL=") for line in updated):
        updated.append("LOG_LEVEL=INFO")
    if not any(line.strip().startswith("ADMIN_IDS=") for line in updated):
        updated.append("ADMIN_IDS=")
    if not any(line.strip().startswith("AUDD_API_TOKEN=") for line in updated):
        updated.append("AUDD_API_TOKEN=")

    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
