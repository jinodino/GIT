from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Category(str, Enum):
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    QUALITY = "QUALITY"


class ReviewItem(BaseModel):
    file_name: str
    line: int = Field(ge=1)
    severity: Severity
    category: Category
    message: str
    suggestion: str


class ReviewResult(BaseModel):
    reviews: list[ReviewItem]