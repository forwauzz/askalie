"""Shared serialization base for Ask ALIE models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AlieModel(BaseModel):
    """Base model: tolerant of unknown fields on read, stable JSON on write."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
