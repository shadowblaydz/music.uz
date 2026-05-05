from __future__ import annotations

import logging

from app.bot import MusicBot
from app.config import get_settings
from app.database import Database


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=getattr(logging, settings.log_level, logging.INFO),
    )

    database = Database(settings.database_path)
    database.init()

    bot = MusicBot(settings, database)
    try:
        bot.run_forever()
    finally:
        database.close()

if __name__ == "__main__":
    main()
