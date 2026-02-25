import requests

class LocalLLM:

    def __init__(self, model="mistral"):
        self.model = model

    def chat(self, messages):

        r = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False
            }
        )
        response = r.json()
        return response["message"]["content"]
