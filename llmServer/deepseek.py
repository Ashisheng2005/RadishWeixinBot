from openai import OpenAI

class DeepSeek():
    def __init__(self, api_key=None, base_url=None, 
                 model=None,
                 language=None):
        self.api_key = api_key
        self.language = language
        self.base_url = base_url 
        self.model = model
        # self.history_limit = max(0, history_limit)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url

        )
        
    def sendinfo(self, messages, temperature=0.7, max_tokens=4000):
        # print(f"Sending messages to DeepSeek API: {messages}")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        # print(f"DeepSeek API response: {response}")
        return response.choices[0].message.content.strip()
    
    