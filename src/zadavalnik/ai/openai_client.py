import json
import logging
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI

from zadavalnik.config.settings import settings

logger = logging.getLogger(__name__)

# FIXME: Использование tool use не работает через bothub
# не присваивается случайный function_call_id это вызывает глюки в поведении сети

# (вопрос, комментарий на ответ и новый вопрос, резюме)
class OpenAIClient:
    def __init__(self, api_key: str, model_name: str = settings.OPENAI_MODEL):
        self.client = AsyncOpenAI(api_key=api_key, base_url=settings.OPENAI_API_URL)
        self.model = model_name
        self.test_tool_name = "record_test_interaction" # Сохраняем для доступа извне

        self.tools_definition = [
            {
                "type": "function",
                "function": {
                    "name": self.test_tool_name,
                    # "description": "Записывает вопрос теста, уточнение, или финальное резюме для пользователя. Используй этот инструмент для КАЖДОГО сообщения пользователю.",
                    "description": f"Устанавливает дополнительную стуктуру сообщений в рамках теста",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_to_user": {
                                "type": "string",
                                "description": "Текст сообщения для пользователя"
                            },
                            "current_question_number": {
                                "type": "integer",
                                "description": "Текущий порядковый номер задаваемого вопроса. Начинается с 1 для первого вопроса, 2 для второго и т.д."
                            },
                            "total_questions_in_test": {
                                "type": "integer",
                                "description": "Общее количество вопросов, которое ты планируешь задать в этом тесте. Должно быть установлено в первом вызове и не меняться."
                            },
                            "is_final_summary": {
                                "type": "boolean",
                                "description": "Установи в True, если это финальное сообщение с подведением итогов теста. В остальных случаях False."
                            }
                        },
                        "required": ["message_to_user", "current_question_number", "total_questions_in_test", "is_final_summary"]
                    }
                }
            }
        ]

    # #   (вопрос, комментарий на ответ пользователя вместе с новым вопросом, и финальное резюме).
    def _get_system_prompt_for_test(self, topic: str, history: Optional[List[Dict]] = None) -> str:
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


        ВАЖНО: Ты ДОЛЖЕН использовать предоставленный инструмент '{self.test_tool_name}' для КАЖДОГО своего сообщения пользователю.
     
        - Поле 'total_questions_in_test' должно быть заполнено с первого же сообщения и оставаться консистентным.
        - Поле 'current_question_number' должно корректно инкрементироваться для каждого НОВОГО вопроса. Если ты комментируешь ответ на вопрос N и затем задаешь вопрос N+1, current_question_number должен быть N+1.
        - Поле 'is_final_summary' должно быть true ТОЛЬКО для самого последнего сообщения, завершающего тест.
        
        Если это был последний вопрос: 
        - предоставь краткое резюме: На какие вопросы пользователь ответил верно, а какие темы стоит повторить.
        - Если были неточности в формулировках ответов пользователя, укажи на них.

        Веди диалог последовательно.
        
        
        """

    async def _make_openai_call(self, current_messages_for_api: List[Dict]) -> Tuple[Optional[Dict], List[Dict], Optional[str], Optional[str]]:
        """
        Вспомогательный метод для вызова API.
        Возвращает (разобранные_аргументы_функции, история_включающая_этот_ответ_AI, tool_call_id, tool_function_name).
        """
        logger.debug(f"OpenAIClient: Sending messages to API: {json.dumps(current_messages_for_api, indent=2, ensure_ascii=False)}")
        
        final_history_after_call = list(current_messages_for_api)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=current_messages_for_api,
                tools=self.tools_definition,
                tool_choice={"type": "function", "function": {"name": self.test_tool_name}},
                max_tokens=1000, # Ограничиваем количество токенов в ответе
                # temperature=0.5, # Уменьшаем креативность для более предсказуемых ответов
            )
            
            response_message = response.choices[0].message
            assistant_message_dict_for_history = {"role": "assistant"}
            
            if response_message.tool_calls:
                tool_calls_for_history = []
                # Мы ожидаем только один tool_call с нашим именем, но обработаем на случай нескольких
                extracted_tool_call_id: Optional[str] = None
                extracted_tool_function_name: Optional[str] = None
                parsed_args: Optional[Dict] = None

                for tc in response_message.tool_calls:
                    tool_calls_for_history.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    })
                    if tc.function.name == self.test_tool_name:
                        # Сохраняем ID и имя первого подходящего вызова
                        if extracted_tool_call_id is None:
                            extracted_tool_call_id = tc.id
                            extracted_tool_function_name = tc.function.name
                            try:
                                parsed_args = json.loads(tc.function.arguments)
                                logger.debug(f"OpenAIClient: Parsed tool call arguments: {parsed_args}")
                            except json.JSONDecodeError:
                                logger.error(f"OpenAI tool arguments are not valid JSON: {tc.function.arguments}", exc_info=True)
                                # parsed_args останется None, но ID и имя могут быть полезны для ответа
                
                if tool_calls_for_history: # Если были хоть какие-то tool_calls
                    assistant_message_dict_for_history["tool_calls"] = tool_calls_for_history
                
                final_history_after_call.append(assistant_message_dict_for_history)

                if parsed_args and extracted_tool_call_id and extracted_tool_function_name:
                    return parsed_args, final_history_after_call, extracted_tool_call_id, extracted_tool_function_name
                else:
                    # Был tool_call, но не наш, или ошибка парсинга аргументов
                    logger.warning(f"OpenAIClient: Tool call occurred but not the expected one or args failed to parse. Calls: {response_message.tool_calls}")
                    return None, final_history_after_call, extracted_tool_call_id, extracted_tool_function_name # Может быть полезно вернуть ID для tool message
            
            elif response_message.content is not None:
                logger.warning(f"OpenAIClient: AI responded with text content instead of tool call: {response_message.content}")
                assistant_message_dict_for_history["content"] = response_message.content
                final_history_after_call.append(assistant_message_dict_for_history)
                return None, final_history_after_call, None, None
            
            else:
                logger.warning(f"OpenAIClient: AI response had no tool_calls and no content. Finish reason: {response.choices[0].finish_reason}")
                return None, current_messages_for_api, None, None # Не добавляем пустой ответ AI

        except Exception as e:
            logger.error(f"Error in _make_openai_call", exc_info=True)
            return None, current_messages_for_api, None, None


    async def start_test_session(self, topic: str) -> Tuple[Optional[Dict], List[Dict], Optional[str], Optional[str]]:
        system_message_content = self._get_system_prompt_for_test(topic)
        messages_for_api_call = [{"role": "system", "content": system_message_content}]
        
        parsed_args, updated_history, tool_call_id, tool_function_name = await self._make_openai_call(messages_for_api_call)
        return parsed_args, updated_history, tool_call_id, tool_function_name


    async def continue_test_session(self, history: List[Dict], user_message_text: str) -> Tuple[Optional[Dict], List[Dict], Optional[str], Optional[str]]:
        messages_for_api_call = list(history)
        messages_for_api_call.append({"role": "user", "content": user_message_text})
        
        parsed_args, updated_history, tool_call_id, tool_function_name = await self._make_openai_call(messages_for_api_call)
        return parsed_args, updated_history, tool_call_id, tool_function_name