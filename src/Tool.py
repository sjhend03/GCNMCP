class Tool:
    """
    Wrapper class that aensures type safety and consistency
    """
    def __init__(self, name: str, description = "", input_schema: dict = None):
        self.name = name
        self.description = description
        self.input_schema = input_schema
