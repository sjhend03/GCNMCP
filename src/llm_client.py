import requests


class LocalLLM:
    """
    Runs a local LLM using Ollama.
    """

    def __init__(self, model="mistral", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, messages):
        r = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0
                }
            },
            timeout=120
        )
        r.raise_for_status()

        response = r.json()

        if "message" not in response or "content" not in response["message"]:
            raise ValueError(f"Unexpected Ollama response: {response}")

        return response["message"]["content"]