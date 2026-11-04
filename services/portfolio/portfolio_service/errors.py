class APIError(Exception):
    """An error that maps directly onto a JSON HTTP response."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


class NotFound(APIError):
    status_code = 404
    code = "not_found"


class Conflict(APIError):
    status_code = 409
    code = "conflict"


class MarketDataUnavailable(APIError):
    status_code = 503
    code = "market_data_unavailable"
