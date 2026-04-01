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
        print(f"Sending {len(messages)} messages")
        print(f"Approx chars: {sum(len(str(m)) for m in messages)}")

        r = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False
            },
            timeout=360,
        )
        r.raise_for_status()
        response = r.json()
        if not response.get("message") or not response["message"].get("content"):
            print(response)
            return "Error: Missing message or content"

        return response["message"]["content"]
