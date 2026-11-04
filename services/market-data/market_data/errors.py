class APIError(Exception):
    """An error that maps directly onto a JSON HTTP response."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


class InvalidSymbol(APIError):
    status_code = 400
    code = "invalid_symbol"


class SymbolNotFound(APIError):
    status_code = 404
    code = "symbol_not_found"


class ProviderUnavailable(APIError):
    status_code = 503
    code = "provider_unavailable"
