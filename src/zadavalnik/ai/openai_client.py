import json
# from openai import OpenAI
from zadavalnik.config.settings import Settings

class OpenAIClient:
    def __init__(self):
        return
        # self.client = OpenAI(api_key=Settings.OPENAI_API_KEY)
        # self.client = OpenAI(api_key=Settings.OPENAI_API_KEY)
    
    def ask(self, question):
        """
        Отправляет вопрос к OpenAI API и возвращает ответ в формате JSON.
        """
        # TODO: Подключить подходящую для тестов LLM
        return {"message": "привет", "msg_type": "yesno"}
        # try:
        #     response = self.client.chat.completions.create(
        #         model="gpt-4o-mini",
        #         messages=[
        #             {"role": "system", "content": "Ты отвечаешь на все вопросы только да или нет"},
        #             {"role": "user", "content": question}
        #         ],
        #         max_tokens=10
        #     )
        #     answer = response.choices[0].message.content.strip()
        #     return {"message": answer, "msg_type": "yesno"}
        # except Exception as e:
        #     print(f"Ошибка при запросе к OpenAI: {e}")
        #     return None