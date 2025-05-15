import os
import json
from openai import OpenAI

# --- Конфигурация ---
# OPENAI_MODEL: str = "deepseek-chat-v3-0324"
# OPENAI_MODEL: str = "gemini-2.0-flash-001"
OPENAI_MODEL: str = "deepseek-r1"
OPENAI_API_URL: str = "https://bothub.chat/api/v2/openai/v1"
# OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "YOUR_BOTHUB_API_KEY") # ЗАМЕНИТЕ ИЛИ УСТАНОВИТЕ ПЕРЕМЕННУЮ 
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") # ЗАМЕНИТЕ ИЛИ УСТАНОВИТЕ ПЕРЕМЕННУЮ 

# print(OPENAI_API_KEY)

if OPENAI_API_KEY == "YOUR_BOTHUB_API_KEY":
    print("!!! ОШИБКА: Установите ваш Bothub API ключ в переменной OPENAI_API_KEY или напрямую в скрипте. Тест не будет работать. !!!")
    # exit() # Раскомментируйте, чтобы прервать выполнение, если ключ не установлен

# --- Инициализация клиента OpenAI ---
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_API_URL,
)

# --- 1. Фиктивная функция, которую модель "вызовет" ---
def get_city_weather(city: str) -> str:
    """Возвращает 'фиктивную' погоду для города."""
    print(f"--- Python: Вызвана функция get_city_weather(city='{city}') ---")
    if city.lower() == "москва":
        return json.dumps({"city": city, "temperature": "+5°C", "condition": "облачно"})
    else:
        return json.dumps({"city": city, "temperature": "неизвестно", "condition": "данных нет"})

# --- 2. Описание функции для модели (tools) ---
tools_definition = [
    {
        "type": "function",
        "function": {
            "name": "get_city_weather",
            "description": "Получить текущую погоду в указанном городе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Название города, например, 'Москва'"},
                },
                "required": ["city"],
            },
        }
    }
]

def test_function_calling_core(user_prompt: str):
    """Тестирует основной цикл function calling."""
    print(f"\nПользователь: {user_prompt}")
    messages = [{"role": "user", "content": user_prompt}]

    try:
        # --- 3. Первый запрос к модели ---
        print("--- Запрос 1: Отправка задачи модели ---")
        

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools_definition,
            tool_choice="auto",  # Модель решает, вызывать ли функцию
            # tool_choice={"type": "function", "function": {"name": "get_city_weather"}},
        )

        print(response)

        response_message = response.choices[0].message
        print(f"Ответ модели (шаг 1): {response_message}") # Для отладки
        print(f"response.choices[0].finish_reason: {response.choices[0].finish_reason}") # Для отладки

        tool_calls = response_message.tool_calls

        # --- 4. Если модель решила вызвать функцию ---
        if tool_calls:
            print("--- Модель запрашивает вызов функции. ---")
            # Добавляем ответ ассистента (с запросом на вызов) в историю
            messages.append(response_message)

            # Для простоты предполагаем один tool_call
            tool_call = tool_calls[0]
            function_name = tool_call.function.name
            function_args_str = tool_call.function.arguments
            
            print(f"--- Модель хочет вызвать: {function_name} с аргументами: {function_args_str} ---")

            # "Выполняем" функцию
            if function_name == "get_city_weather":
                function_args = json.loads(function_args_str)
                function_response_content = get_city_weather(city=function_args.get("city"))
            else:
                # Если модель запросила неизвестную функцию (не должно случиться с tool_choice="auto" и одним tool)
                print(f"!!! Ошибка: Модель запросила неизвестную функцию: {function_name} !!!")
                function_response_content = json.dumps({"error": f"Unknown function {function_name}"})

            print(f"--- Результат выполнения Python-функции: {function_response_content} ---")
            
            # Добавляем результат вызова функции в историю
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response_content, # Результат функции должен быть строкой
                }
            )

            # --- 5. Второй запрос к модели с результатом вызова функции ---
            print("--- Запрос 2: Отправка результата вызова функции модели ---")
            second_response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages
            )
            final_response_content = second_response.choices[0].message.content
            print(f"Модель (финальный ответ после вызова функции): {final_response_content}")

        else:
            # Если вызова функции не было, просто выводим прямой ответ модели
            print(f"Модель (прямой ответ, без вызова функции): {response_message.content}")

    except Exception as e:
        print(f"!!! Произошла ошибка во время теста: {e} !!!")
        import traceback
        traceback.print_exc()

# --- Запуск теста ---
if __name__ == "__main__":
    if OPENAI_API_KEY == "YOUR_BOTHUB_API_KEY":
        print("Пожалуйста, установите ваш API ключ для продолжения.")
    else:
        # Запрос, который должен инициировать вызов функции
        test_function_calling_core("Какая погода в Москве?")
        
        # Запрос, который, скорее всего, не вызовет функцию
        test_function_calling_core("Привет, как дела?")