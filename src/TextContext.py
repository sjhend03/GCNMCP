class TextContext:
    """
    Wrapper class that helps with type safety and consistency
    """
    def __init__(self, text: str):
        self.type = "text"
        self.text = text        