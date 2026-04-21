import asyncio
import logging
import os
from aiohttp import web
from aiogram.exceptions import TelegramNetworkError

from app.bot import bot, dp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def health_handler(request):
    return web.Response(text="OK")


async def run_health_server():
    """Minimal HTTP server so Railway knows the process is alive."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health-check server listening on port %s", port)


async def main():
    logger.info("Starting bot in polling mode...")
    await run_health_server()
    try:
        me = await bot.get_me()
        logger.info("Telegram OK, logged in as @%s (id=%s)", me.username, me.id)
    except TelegramNetworkError as e:
        logger.error(
            "Не удаётся подключиться к api.telegram.org (%s). "
            "Проверьте интернет, файрвол, VPN (в РФ Telegram API часто блокируется), DNS.",
            e,
        )
        raise SystemExit(1) from e
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    asyncio.run(main())
