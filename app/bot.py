from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers.start import router as start_router
from app.handlers.calc import router as calc_router
from app.handlers.daily import router as daily_router
from app.handlers.admin import router as admin_router
from app.handlers.payments import router as payments_router
from app.middleware import ConsentMiddleware

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.message.middleware(ConsentMiddleware())
dp.callback_query.middleware(ConsentMiddleware())

dp.include_router(admin_router)
dp.include_router(payments_router)
dp.include_router(daily_router)
dp.include_router(calc_router)
dp.include_router(start_router)
