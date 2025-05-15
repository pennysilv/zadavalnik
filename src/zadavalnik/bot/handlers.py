import logging
import json # Для json.dumps в tool message
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from zadavalnik.database.db import (
    get_db_session, 
    get_or_create_telegram_user_in_db,
    log_test_attempt_start,
    update_test_attempt_status,
    count_user_daily_tests,
    log_rate_limit_attempt
)
from zadavalnik.database.models import TestStatus
from zadavalnik.ai.openai_client import OpenAIClient
from zadavalnik.bot.states import UserState
from zadavalnik.config.settings import settings

logger = logging.getLogger(__name__)

def setup_handlers(app: Application):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("newtest", new_test_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

def _clear_user_test_state(context: ContextTypes.DEFAULT_TYPE):
    keys_to_clear = [
        'current_state', 'current_topic', 'gpt_chat_history', 
        'current_question_num', 'total_questions', 'active_test_attempt_id'
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]

async def _initialize_new_test_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user
    user_id = user_tg.id
    _clear_user_test_state(context)

    # Для тестовго пользователя не делаем ограничений
    # print("user_id: ",user_id)
    # print("user_id: ",settings.TEST_USER_TGID)

    if settings.TEST_USER_TGID != int(user_id):
   
        async for db in get_db_session():
            await get_or_create_telegram_user_in_db(db, user_tg)

            tests_today = await count_user_daily_tests(db, user_id)
            logger.info(f"User {user_id} has {tests_today} tests today. Limit: {settings.MAX_TESTS_PER_DAY}")

            if tests_today >= settings.MAX_TESTS_PER_DAY:
                await log_rate_limit_attempt(db, user_id)
                await update.message.reply_text(
                    f"Вы уже прошли максимальное количество тестов на сегодня ({settings.MAX_TESTS_PER_DAY}). "
                    "Пожалуйста, возвращайтесь завтра!"
                )
                return False

    context.user_data['current_state'] = UserState.AWAITING_TOPIC
    await update.message.reply_text(
        "Добро пожаловать в Задавальник!\n"
        "Введите тему, по которой вы хотите пройти тест."
    )
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} used /start")
    await _initialize_new_test_session(update, context)

async def new_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} used /newtest")
    await _initialize_new_test_session(update, context)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_received = update.message.text
    current_state = context.user_data.get('current_state')

    logger.info(f"User {user_id} (state: {current_state}) sent text: '{text_received}'")

    openai_client: OpenAIClient = context.application.bot_data.get('openai_client')
    if not openai_client:
        logger.error("OpenAI client not found in bot_data.")
        await update.message.reply_text("Ошибка конфигурации бота. Обратитесь к администратору.")
        return

    if current_state == UserState.AWAITING_TOPIC:

        # NOTE: Избыточная проверка, отключаем пока
        # async for db in get_db_session():
        #     tests_today = await count_user_daily_tests(db, user_id)
        #     if tests_today >= settings.MAX_TESTS_PER_DAY:
        #         await log_rate_limit_attempt(db, user_id)
        #         await update.message.reply_text(
        #             f"Вы уже прошли максимальное количество тестов на сегодня ({settings.MAX_TESTS_PER_DAY}). "
        #             "Возвращайтесь завтра!"
        #         )
        #         _clear_user_test_state(context)
        #         return
        
        
        # NOTE: (пока не реализовывать, просто заметка) Валидация темы теста 
        # Тему надо перефразировать в более развернутый вид.
        # Пользователь ввел "обж", а мы перефразируем в "Основы безопасности жизнедеятельности"
        #         
        if len(text_received) < 3:
            await update.message.reply_text("Тема не задана. Попробуйте снова.")
            return


        await update.message.reply_text(f"Подготавливаю вопросы по теме: \"{text_received}\".")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Получаем также tool_call_id и tool_function_name
        gpt_response_data, gpt_history, tool_call_id, tool_function_name = await openai_client.start_test_session(topic=text_received)
        
        if gpt_response_data and tool_call_id and tool_function_name:
            # Добавляем сообщение tool в историю ПЕРЕД сохранением и отправкой пользователю
            # tool_message_content = {"status": "success", "message_sent_to_user": gpt_response_data["message_to_user"]}
            # Предыдущий варианты вызвал дубирование сообщений в истории
            tool_message_content_for_ai = {"status": "OK"}
            
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_function_name,
                "content": json.dumps(tool_message_content_for_ai, ensure_ascii=False) 
            }
            gpt_history.append(tool_message) # Важно: gpt_history уже содержит ответ ассистента с tool_calls

            async for db in get_db_session():
                attempt = await log_test_attempt_start(db, user_id, text_received)
                context.user_data['active_test_attempt_id'] = attempt.id
            
            context.user_data.update({
                'current_topic': text_received,
                'current_state': UserState.IN_TEST,
                'gpt_chat_history': gpt_history, # Сохраняем историю, включающую tool_call и tool_message
                'current_question_num': gpt_response_data.get("current_question_number"),
                'total_questions': gpt_response_data.get("total_questions_in_test")
            })
            await update.message.reply_text(gpt_response_data["message_to_user"])
            
            if gpt_response_data.get("is_final_summary"):
                async for db in get_db_session():
                    await update_test_attempt_status(db, context.user_data['active_test_attempt_id'], TestStatus.COMPLETED, end_time=True)
                context.user_data['current_state'] = UserState.TEST_COMPLETED
                await update.message.reply_text("Тест завершен! Для нового теста используйте /newtest.")
        else:
            logger.warning(f"Failed to start AI test session for user {user_id}, topic: {text_received}. Response data: {gpt_response_data}, Tool ID: {tool_call_id}")
            await update.message.reply_text("Не удалось начать тест. Попробуйте другую тему или повторите позже.")
            # Не меняем состояние, пользователь может попробовать ввести другую тему
    
    # Прием ответов на вопросы теста
    elif current_state == UserState.IN_TEST:
        active_test_id = context.user_data.get('active_test_attempt_id')
        if not active_test_id:
            logger.error(f"User {user_id} in IN_TEST state but no active_test_attempt_id found.")
            await update.message.reply_text("Произошла ошибка сессии. Пожалуйста, начните новый тест: /newtest")
            _clear_user_test_state(context)
            context.user_data['current_state'] = UserState.AWAITING_TOPIC
            return

        # await update.message.reply_text("Принято...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        current_gpt_history = context.user_data.get('gpt_chat_history', [])
        gpt_response_data, gpt_history, tool_call_id, tool_function_name = await openai_client.continue_test_session(
            history=current_gpt_history,
            user_message_text=text_received
        )

        if gpt_response_data and tool_call_id and tool_function_name:

            # tool_message_content = {"status": "success", "message_sent_to_user": gpt_response_data["message_to_user"]}
            tool_message_content_for_ai = {"status": "OK"}
            
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_function_name,
                "content": json.dumps(tool_message_content_for_ai, ensure_ascii=False)
            }
            gpt_history.append(tool_message)

            context.user_data.update({
                'gpt_chat_history': gpt_history,
                'current_question_num': gpt_response_data.get("current_question_number"),
                # total_questions не должен меняться в середине теста, его AI устанавливает в первом вызове
            })

            # Отправляем пользователю сообщение, сгенерированное AI
            await update.message.reply_text(gpt_response_data["message_to_user"])

            if gpt_response_data.get("is_final_summary"):
                async for db in get_db_session():
                    await update_test_attempt_status(db, active_test_id, TestStatus.COMPLETED, end_time=True)
                context.user_data['current_state'] = UserState.TEST_COMPLETED
                logger.info(f"Test {active_test_id} completed for user {user_id}")
                await update.message.reply_text("Тест завершен! Чтобы начать новый, используйте команду /newtest.")
        else:
            logger.warning(f"Failed to continue AI test session for user {user_id}, test_id {active_test_id}. Response data: {gpt_response_data}, Tool ID: {tool_call_id}")
            await update.message.reply_text("Произошла ошибка при общении с ИИ. Попробуйте ответить еще раз. Если ошибка повторится, начните новый тест: /newtest.")

    elif current_state == UserState.TEST_COMPLETED:
        await update.message.reply_text("Тест уже завершен. Чтобы начать новый, используйте команду /newtest.")
    
    elif current_state == UserState.START or not current_state:
         await update.message.reply_text("Пожалуйста, используйте команду /start или /newtest, чтобы начать.")
         _clear_user_test_state(context)  # Сбрасываем состояние на всякий случай

    else:
        logger.error(f"User {user_id} is in an unknown state: {current_state}")
        await update.message.reply_text("Произошла внутренняя ошибка состояния. Пожалуйста, перезапустите бота командой /start.")
        _clear_user_test_state(context)
        context.user_data['current_state'] = UserState.START