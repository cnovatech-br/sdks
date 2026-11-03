from __future__ import annotations

import builtins
from typing import Any, ClassVar

import pytest
from pydantic import Field

from cnovatech.sdk_core.dataframe import TabularResponse, flatten, flatten_envelope
from cnovatech.sdk_core.models import APIResponse


class Stats(APIResponse):
    median: float | None = None
    count: int = 0


class Row(APIResponse):
    code: str
    stats: Stats
    tags: list[str] = Field(default_factory=list)


class Owner(APIResponse):
    owner_id: str
    city: str | None = None


class Report(TabularResponse):
    owner: Owner
    note: str
    data: list[Row]
    meta: dict[str, int] = Field(default_factory=dict)


class Offers(TabularResponse):
    rows_field: ClassVar[str] = "offers"

    code: str
    offers: list[Row]


def report() -> Report:
    return Report.model_validate(
        {
            "owner": {"owner_id": "o1", "city": "SP"},
            "note": "n",
            "meta": {"page": 1},
            "data": [
                {"code": "a", "stats": {"median": 1.5, "count": 3}, "tags": ["x"]},
                {"code": "b", "stats": {"median": None, "count": 0}},
            ],
        }
    )


def test_flatten_joins_nested_keys() -> None:
    assert flatten({"a": {"b": {"c": 1}}, "d": [1, 2]}) == {"a_b_c": 1, "d": [1, 2]}


def test_flatten_envelope_prefixes_objects_and_skips_lists_and_meta() -> None:
    flat = flatten_envelope(
        {"owner": {"owner_id": "o1", "city": "SP"}, "note": "n", "meta": {"page": 1}, "data": []}
    )

    assert flat == {"owner_id": "o1", "owner_city": "SP", "note": "n"}


def test_to_dataframe_flattens_rows_and_repeats_the_envelope() -> None:
    frame = report().to_dataframe()

    assert list(frame.columns) == [
        "owner_id",
        "owner_city",
        "note",
        "code",
        "stats_median",
        "stats_count",
        "tags",
    ]
    assert frame["code"].tolist() == ["a", "b"]
    assert frame["stats_count"].tolist() == [3, 0]
    assert frame["owner_id"].tolist() == ["o1", "o1"]
    assert frame["tags"].tolist() == [["x"], []]


def test_to_dataframe_without_envelope_keeps_row_columns_only() -> None:
    frame = report().to_dataframe(include_envelope=False)

    assert list(frame.columns) == ["code", "stats_median", "stats_count", "tags"]


def test_empty_list_gives_an_empty_frame_with_envelope_columns() -> None:
    empty = Report.model_validate({"owner": {"owner_id": "o1"}, "note": "n", "data": []})

    frame = empty.to_dataframe()

    assert len(frame) == 0
    assert list(frame.columns) == ["owner_id", "owner_city", "note"]


def test_rows_field_can_be_renamed() -> None:
    offers = Offers.model_validate(
        {"code": "c", "offers": [{"code": "x", "stats": {"median": 2.0, "count": 1}}]}
    )

    frame = offers.to_dataframe()

    assert frame["code"].tolist() == ["x"]
    assert "stats_median" in frame.columns


def test_missing_pandas_gives_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pandas":
            raise ImportError("No module named 'pandas'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match="'pandas' extra"):
        report().to_dataframe()
