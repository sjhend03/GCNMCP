import requests

class LocalLLM:
    """
    Runs a local LLM using Ollama, if another method is used, the localhost post call
    must be updated.
    model: LLM model that is used locally
    """
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
