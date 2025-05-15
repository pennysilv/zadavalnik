from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func, update as sqlalchemy_update # для func.count и update
from datetime import datetime, timedelta

from zadavalnik.config.settings import settings
from zadavalnik.database.models import Base, TelegramUser, TestAttempt, TestStatus
from telegram import User as TelegramUserObject # Тип пользователя из python-telegram-bot

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

async def init_db():
    async with async_engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Для разработки
        await conn.run_sync(Base.metadata.create_all)
    print("Logging database initialized.")

async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

async def get_or_create_telegram_user_in_db(db: AsyncSession, tg_user: TelegramUserObject) -> TelegramUser:
    """Получает или создает/обновляет запись о пользователе Telegram в БД."""
    user = await db.get(TelegramUser, tg_user.id)
    if user:
        # Обновляем данные, если они изменились (простой вариант)
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
        user.is_bot = str(tg_user.is_bot) # Конвертируем в строку
    else:
        user = TelegramUser(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
            is_bot=str(tg_user.is_bot)
        )
        db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def log_test_attempt_start(db: AsyncSession, user_id: int, topic: str) -> TestAttempt:
    """Логирует начало попытки теста."""
    attempt = TestAttempt(user_id=user_id, topic=topic, status=TestStatus.STARTED)
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt

async def update_test_attempt_status(db: AsyncSession, attempt_id: int, status: TestStatus, end_time: bool = False):
    """Обновляет статус и, опционально, время окончания попытки теста."""
    values_to_update = {"status": status}
    if end_time:
        values_to_update["end_time"] = datetime.now().astimezone() # Используем aware datetime

    stmt = (
        sqlalchemy_update(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .values(**values_to_update)
    )
    await db.execute(stmt)
    await db.commit()

async def count_user_daily_tests(db: AsyncSession, user_id: int) -> int:
    """Считает количество тестов (не RATE_LIMITED) пользователя за сегодня."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Считаем тесты, которые начались сегодня и не являются просто записью о превышении лимита
    result = await db.execute(
        select(func.count(TestAttempt.id))
        .where(TestAttempt.user_id == user_id)
        .where(TestAttempt.start_time >= today_start)
        .where(TestAttempt.status != TestStatus.RATE_LIMITED) # Не считаем попытки, которые были заблокированы лимитом
    )
    return result.scalar_one()

async def log_rate_limit_attempt(db: AsyncSession, user_id: int):
    """Логирует попытку начать тест сверх лимита."""
    attempt = TestAttempt(user_id=user_id, status=TestStatus.RATE_LIMITED)
    db.add(attempt)
    await db.commit()