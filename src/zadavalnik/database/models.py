from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func # Для func.now()
import enum

Base = declarative_base()

class TestStatus(enum.Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED" # Если пользователь прервал или произошла ошибка
    RATE_LIMITED = "RATE_LIMITED" # Попытка начать тест сверх лимита

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True) # Telegram User ID, не автоинкремент, а именно ID от TG
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, nullable=True)
    is_bot = Column(String, default="False") # Храним как строку, т.к. Boolean может быть True/False/None
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    test_attempts = relationship("TestAttempt", back_populates="user")

    def __repr__(self):
        return f"<TelegramUser(id={self.id}, username='{self.username}')>"

class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True) # PK для этой таблицы
    user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=False)
    
    topic = Column(String, nullable=True) # Будет заполнено, если тест начался
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(SQLAlchemyEnum(TestStatus), nullable=False)

    user = relationship("TelegramUser", back_populates="test_attempts")

    def __repr__(self):
        return f"<TestAttempt(id={self.id}, user_id={self.user_id}, topic='{self.topic}', status={self.status})>"