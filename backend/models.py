"""
Data models for the CV Review System
"""

from typing import Optional
from pydantic import BaseModel


class CVInfo(BaseModel):
    name: str
    source: str  # 'gdrive' or 'github'
    path: str
    job_description: Optional[str] = None


class ReviewResult(BaseModel):
    cv_name: str
    review: str


class ReviewAllResult(BaseModel):
    cv_name: str
    review: str
    fit_score: int
    token_count: Optional[int] = 0
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
