class ApiError(Exception):
    """Any failure that must reach the browser as {"error": ..., "code": ...}."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
