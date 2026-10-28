"""Shared value types for form dissection.

Folded in from ss-documentDissection, with two fixes over the original:
the Pydantic models are replaced by plain dataclasses (no new core
dependency, and no Pydantic v1/v2 ambiguity), and every type round-trips
through JSON — the original wrote fieldmaps with ``str()``, which only
``eval()`` could read back.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldBox:
    """A detected form field: bounding box in pixel coordinates."""

    x: int
    y: int
    w: int
    h: int
    name: str | None = None
    score: float | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FieldBox:
        return cls(
            name=data.get("name"),
            x=int(data["x"]),
            y=int(data["y"]),
            w=int(data["w"]),
            h=int(data["h"]),
            score=data.get("score"),
        )


@dataclass
class PageData:
    """One page's extracted text, plus the rendered image shape if rendered."""

    page_number: int
    text: str
    image_shape: list[int] | None = None


@dataclass
class DetectionResult:
    """Which pages matched a template, and each page's score."""

    template_name: str
    matched_pages: list[int] = field(default_factory=list)
    scores: dict[int, float] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "template_name": self.template_name,
            # JSON keys must be strings; keep them that way on the way out.
            "matched_pages": self.matched_pages,
            "scores": {str(k): v for k, v in self.scores.items()},
            "meta": self.meta,
        }


__all__ = ["DetectionResult", "FieldBox", "PageData"]
