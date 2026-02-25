class Tool:
    def __init__(self, name: str, description = "", input_schema: dict = None):
        self.name = name
        self.description = description
        self.input_schema = input_schema
