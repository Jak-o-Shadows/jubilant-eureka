"""
Generated tcod-ecs components from schema.
DO NOT EDIT.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Blah:
    """
    Represents the <blah> component.
    """
    value: float


@dataclass(frozen=True, slots=True)
class Prefab:
    """
    Represents the <prefab> component.
    """
    value: str


@dataclass(frozen=True, slots=True)
class Ztag:
    """
    Represents the <ztag> component.
    """
    asdf: str
    vv33: int


@dataclass(frozen=True, slots=True)
class Ftag:
    """
    Represents the <ftag> component.
    """
    value1: str
    value2: str


@dataclass(frozen=True, slots=True)
class Etag:
    """
    Represents the <etag> component.
    """
    value1: str
    value2: float


@dataclass(frozen=True, slots=True)
class Dtag:
    """
    Represents the <dtag> component.
    """
    value1: int


@dataclass(frozen=True, slots=True)
class Ctag:
    """
    Represents the <ctag> component.
    """
    value1: int
    value2: str
    value3: float


@dataclass(frozen=True, slots=True)
class Btag:
    """
    Represents the <btag> component.
    """
    value1: float
    value2: str
    value3: int


COMPONENT_MAP = {
    "blah": Blah,
    "prefab": Prefab,
    "ztag": Ztag,
    "ftag": Ftag,
    "etag": Etag,
    "dtag": Dtag,
    "ctag": Ctag,
    "btag": Btag,
}