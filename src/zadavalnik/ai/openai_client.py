import json
import logging
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI

from zadavalnik.config.settings import settings

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key: str, model_name: str = settings.OPENAI_MODEL):
        self.client = AsyncOpenAI(api_key=api_key, base_url=settings.OPENAI_API_URL)
        self.model = model_name
        # self.test_tool_name больше не нужен
        # self.tools_definition больше не нужен

    def _get_system_prompt_for_test(self, topic: str, history: Optional[List[Dict]] = None) -> str:
        # Обратите внимание на новую инструкцию по форматированию ответа
        return f"""
        Ты — бот Zadavalnik помошник для повторения материала.
        Проводящишь интерактивное тестирование по теме: "{topic}".

        Твоя задача — задавать вопросы пользователю один за другим.
        Тест должен состоять из нескольких вопросов (например, 3-5, определи это сам в первом сообщении).

        В начале первого вопроса сообщи "Сейчас мы проведем интерактивный тест по [тема теста]" и количество вопросов.

        Когда ты получил ответ пользователя на вопрос, ты должен:
        ## 1
        Если ответ пользователя хоть как-то связан с вопросом: 
            Дать на него краткий комментарий: (правильно/неправильно, дай короткое пояснение при необходимости).
        Если же пользователь отвечает не по теме вопроса или говорит, что не знает, забыл, простит сказать ответ.
            Просто дать ответ ответ на вопрос без комментариев.
        ## 2
        В этом же сообщении (через строку) пиши текст СЛЕДУЮЩЕГО вопроса.
        
        ВАЖНО: Ты ДОЛЖЕН форматировать КАЖДОЕ свое сообщение пользователю как JSON объект.
        Этот JSON объект должен содержать следующие поля:
        - "message_to_user": (string) Текст сообщения для пользователя. Это то, что увидит пользователь.
        - "current_question_number": (integer) Текущий порядковый номер ЗАДАВАЕМОГО вопроса. Начинается с 1 для первого вопроса, 2 для второго и т.д. Если ты комментируешь ответ на вопрос N и затем задаешь вопрос N+1, current_question_number должен быть N+1.
        - "total_questions_in_test": (integer) Общее количество вопросов, которое ты планируешь задать в этом тесте. Должно быть установлено в первом вызове и не меняться.
        - "is_final_summary": (boolean) Установи в True, если это финальное сообщение с подведением итогов теста. В остальных случаях False.

        Пример твоего ответа:
        {{
            "message_to_user": "Верно! Молодец.\\n\\nСледующий вопрос: Как называется столица Франции?",
            "current_question_number": 2,
            "total_questions_in_test": 3,
            "is_final_summary": False
        }}

        Еще пример (финальное резюме):
        {{
            "message_to_user": "Тест завершен. Вы ответили правильно на 2 из 3 вопросов. Стоит повторить тему X.",
            "current_question_number": 3, # или total_questions_in_test, если уже нет нового вопроса
            "total_questions_in_test": 3,
            "is_final_summary": True
        }}
                
        - Поле 'total_questions_in_test' должно быть заполнено с первого же сообщения и оставаться консистентным.
        - Поле 'current_question_number' должно корректно инкрементироваться для каждого НОВОГО вопроса. 
        - Поле 'is_final_summary' должно быть true ТОЛЬКО для самого последнего сообщения, завершающего тест.
        
        Если это был последний вопрос: 
        - предоставь краткое резюме в 'message_to_user': На какие вопросы пользователь ответил верно, а какие темы стоит повторить.
        - Если были неточности в формулировках ответов пользователя, укажи на них.

        Веди диалог последовательно. Твой ответ должен быть ТОЛЬКО JSON объектом, без какого-либо другого текста до или после него.
        """

    async def _make_openai_call(self, current_messages_for_api: List[Dict]) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Вспомогательный метод для вызова API.
        Возвращает (разобранные_аргументы_из_JSON_ответа, история_включающая_этот_ответ_AI).
        """
        logger.debug(f"OpenAIClient: Sending messages to API: {json.dumps(current_messages_for_api, indent=2, ensure_ascii=False)}")
        
        final_history_after_call = list(current_messages_for_api)
        parsed_data: Optional[Dict] = None

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=current_messages_for_api,
                # tools и tool_choice удалены
                max_tokens=1000,
                # temperature=0.5, # Можно оставить для предсказуемости
            )
            
            response_message = response.choices[0].message
            assistant_response_content = response_message.content
            
            # Сохраняем ответ ассистента в историю, даже если он невалидный JSON, для отладки
            assistant_message_dict_for_history = {"role": "assistant", "content": assistant_response_content}
            final_history_after_call.append(assistant_message_dict_for_history)

            if assistant_response_content:
                try:
                    # Попытка найти JSON блок, если модель добавляет лишний текст
                    # Хотя в идеале она должна вернуть ТОЛЬКО JSON согласно промпту
                    json_start = assistant_response_content.find('{')
                    json_end = assistant_response_content.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = assistant_response_content[json_start:json_end]
                        parsed_data = json.loads(json_str)
                        logger.debug(f"OpenAIClient: Parsed structured response: {parsed_data}")
                    else:
                        logger.error(f"OpenAIClient: Could not find JSON block in AI response: {assistant_response_content}")
                        # parsed_data останется None
                except json.JSONDecodeError:
                    logger.error(f"OpenAIClient: AI response content is not valid JSON: {assistant_response_content}", exc_info=True)
                    # parsed_data останется None
            else:
                logger.warning(f"OpenAIClient: AI response had no content. Finish reason: {response.choices[0].finish_reason}")
            
            return parsed_data, final_history_after_call

        except Exception as e:
            logger.error(f"Error in _make_openai_call", exc_info=True)
            # Возвращаем исходную историю, так как вызов не удался
            return None, current_messages_for_api


    async def start_test_session(self, topic: str) -> Tuple[Optional[Dict], List[Dict]]:
        system_message_content = self._get_system_prompt_for_test(topic)
        messages_for_api_call = [{"role": "system", "content": system_message_content}]
        
        parsed_data, updated_history = await self._make_openai_call(messages_for_api_call)
        return parsed_data, updated_history


    async def continue_test_session(self, history: List[Dict], user_message_text: str) -> Tuple[Optional[Dict], List[Dict]]:
        messages_for_api_call = list(history)
        messages_for_api_call.append({"role": "user", "content": user_message_text})
        
        parsed_data, updated_history = await self._make_openai_call(messages_for_api_call)
        return parsed_data, updated_history