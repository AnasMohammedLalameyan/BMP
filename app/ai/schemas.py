"""Pydantic models for every model output. The model fills these; code checks them before anything is shown."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Found(BaseModel):
    """One value read from a document, with the exact words it came from."""
    value: str
    source_quote: str
    page: int = 1


class AgendaFound(BaseModel):
    text: str
    source_quote: str
    page: int = 1


class MeetingExtraction(BaseModel):
    meeting_date: Optional[Found] = None
    notice_date: Optional[Found] = None
    meeting_time: Optional[Found] = None
    mode: Optional[Found] = None
    chairman: Optional[Found] = None
    directors_present: Optional[Found] = None
    invitees_present: Optional[Found] = None
    leave_of_absence: Optional[Found] = None
    signing_date: Optional[Found] = None
    signing_place: Optional[Found] = None
    agenda: list[AgendaFound] = Field(default_factory=list)


class IntakePlan(BaseModel):
    register_key: Optional[str] = None         # one of the eight register keys, or null when not stated
    company: Optional[str] = None            # company name as written by the person, matched by code
    meeting_date: Optional[str] = None
    notice_date: Optional[str] = None
    meeting_time: Optional[str] = None
    mode: Optional[str] = None
    chairman: Optional[str] = None
    agenda: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class Route(BaseModel):
    intent: Literal["intake", "ask", "other"]


class NoticeCover(BaseModel):
    cover: str                                # a short paragraph; must keep the {recipient_name} placeholder


class Claim(BaseModel):
    text: str
    chunk_id: str
    quote: str


class AskAnswer(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    insufficient: bool = False
