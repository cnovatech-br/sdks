"""Conversion of list responses to pandas DataFrames. pandas is imported only when used."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from .models import APIResponse

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import pandas

ENVELOPE_FIELDS_SKIPPED = frozenset({"meta"})


class TabularResponse(APIResponse):
    """A response whose main content is a list of rows.

    Subclasses name the list in ``rows_field`` when it is not ``data``.
    """

    rows_field: ClassVar[str] = "data"

    def to_dataframe(self, *, include_envelope: bool = True) -> pandas.DataFrame:
        """One row per item of the list, as a pandas DataFrame.

        Nested objects are flattened with ``_``: ``stats.median_price`` becomes
        ``stats_median_price``. With ``include_envelope``, the scalar fields
        around the list, such as the queried entity, the summary and the
        ``usage`` block, are repeated on every row, prefixed by their name.
        Lists inside items are kept as Python lists.

        Requires pandas, available through the SDK's ``pandas`` extra.
        """
        return build_dataframe(self, rows_field=self.rows_field, include_envelope=include_envelope)


def build_dataframe(
    response: APIResponse, *, rows_field: str, include_envelope: bool
) -> pandas.DataFrame:
    """Build the DataFrame of ``response`` from the list in ``rows_field``."""
    payload = response.model_dump(mode="python")
    rows = payload.pop(rows_field, None) or []
    envelope = flatten_envelope(payload) if include_envelope else {}
    records = [{**envelope, **flatten(row)} for row in rows if isinstance(row, dict)]
    return records_to_dataframe(records, columns=column_union(records) or list(envelope))


def column_union(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every key seen across the records, in order of first appearance.

    Rows need not share the same keys: free-form objects and fields the API
    adds to some rows only still get a column.
    """
    seen: dict[str, None] = {}
    for record in records:
        for key in record:
            seen.setdefault(key, None)
    return list(seen)


def records_to_dataframe(
    records: Sequence[Mapping[str, Any]], *, columns: Sequence[str]
) -> pandas.DataFrame:
    """Build a DataFrame from flat records, importing pandas on first use."""
    try:
        import pandas as pandas_module
    except ImportError as exc:
        raise ImportError(
            "pandas is not installed. Install it, or install the SDK with its 'pandas' extra."
        ) from exc
    # pandas ships partial inline types, so the constructor resolves to Any.
    return cast("pandas.DataFrame", pandas_module.DataFrame(list(records), columns=list(columns)))


def flatten(mapping: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested mappings into one level, joining keys with ``_``."""
    flat: dict[str, Any] = {}
    for key, value in mapping.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}_"))
        else:
            flat[name] = value
    return flat


def flatten_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten what surrounds the rows: scalars as they are, objects prefixed by their name.

    A field of an object that already starts with the object's name keeps it:
    ``store.store_id`` becomes ``store_id``, ``store.city`` becomes
    ``store_city``. Lists and pagination metadata are left out.
    """
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        if key in ENVELOPE_FIELDS_SKIPPED or isinstance(value, list):
            continue
        if isinstance(value, dict):
            for inner_key, inner_value in flatten(value).items():
                name = inner_key if inner_key.startswith(f"{key}_") else f"{key}_{inner_key}"
                flat[name] = inner_value
        else:
            flat[key] = value
    return flat
