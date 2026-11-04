import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

SYMBOL_PATTERN = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-=]{0,14}$")

# Strict so that JSON strings and booleans aren't silently coerced into numbers.
Number = StrictInt | StrictFloat
PositiveNumber = Annotated[Number, Field(gt=0, allow_inf_nan=False, le=1e12)]
NonNegativeNumber = Annotated[Number, Field(ge=0, allow_inf_nan=False, le=1e12)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("must be a valid stock symbol")
    return symbol


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PortfolioCreate(_Schema):
    name: Name
    description: Annotated[str, Field(max_length=500)] = ""


class PortfolioUpdate(_Schema):
    name: Name | None = None
    description: Annotated[str, Field(max_length=500)] | None = None


class HoldingBuy(_Schema):
    symbol: str
    quantity: PositiveNumber
    price: NonNegativeNumber

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class HoldingUpdate(_Schema):
    quantity: PositiveNumber
    average_cost: NonNegativeNumber


class HoldingSell(_Schema):
    quantity: PositiveNumber
