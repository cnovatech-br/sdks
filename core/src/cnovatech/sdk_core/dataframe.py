"""Conversion of list responses to pandas DataFrames. pandas is imported only when used."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar, cast

from .models import APIResponse

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import pandas

ENVELOPE_FIELDS_SKIPPED = frozenset({"meta"})
NESTED_ROWS_SEPARATOR = "."
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


class TabularResponse(APIResponse):
    """A response whose main content is a list of rows.

    Subclasses name the list in ``rows_field`` when it is not ``data``. A
    dotted name such as ``"groups.members"`` points at a list nested in each
    item of another list; the parent's own fields are repeated on each row.
    """

    rows_field: ClassVar[str] = "data"

    def to_dataframe(self, *, include_envelope: bool = True) -> pandas.DataFrame:
        """One row per item of the list, as a pandas DataFrame.

        Nested objects are flattened with ``_``: ``stats.median_price`` becomes
        ``stats_median_price``. With ``include_envelope``, the scalar fields
        around the list, such as the queried entity, the summary and the
        ``usage`` block, are repeated on every row, prefixed by their name. An
        envelope field that shares its name with a row field is prefixed with
        the response's name instead, as in ``product_image_url`` next to the
        offer's ``image_url``, so no value is lost. Lists inside items are kept
        as Python lists.

        Requires pandas, available through the SDK's ``pandas`` extra.
        """
        return build_dataframe(self, rows_field=self.rows_field, include_envelope=include_envelope)


def build_dataframe(
    response: APIResponse, *, rows_field: str, include_envelope: bool
) -> pandas.DataFrame:
    """Build the DataFrame of ``response`` from the list in ``rows_field``.

    Only the named list is serialised; sibling lists are left out of the dump
    since the envelope never includes them.
    """
    parent_field, _, child_field = rows_field.partition(NESTED_ROWS_SEPARATOR)
    payload = response.model_dump(mode="python", exclude=_other_lists(response, parent_field))
    parents = [row for row in payload.pop(parent_field, None) or [] if isinstance(row, dict)]
    if child_field:
        rows = [
            {**flatten(_without(parent, child_field)), **flatten(child)}
            for parent in parents
            for child in parent.get(child_field) or []
            if isinstance(child, dict)
        ]
    else:
        rows = [flatten(row) for row in parents]
    envelope: dict[str, Any] = {}
    if include_envelope:
        envelope = disambiguate_envelope(
            flatten_envelope(payload), rows, prefix=response_prefix(response)
        )
    records = [{**envelope, **row} for row in rows]
    return records_to_dataframe(records, columns=column_union(records) or list(envelope))


def disambiguate_envelope(
    envelope: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], *, prefix: str
) -> dict[str, Any]:
    """Prefix the envelope columns that a row also uses, so both values get a column."""
    row_keys = {key for row in rows for key in row}
    return {
        (f"{prefix}_{key}" if key in row_keys else key): value for key, value in envelope.items()
    }


def response_prefix(response: APIResponse) -> str:
    """The response's class name in snake case: ``PriceHistory`` gives ``price_history``."""
    return _CAMEL_CASE_BOUNDARY.sub("_", type(response).__name__).lower()


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


def _other_lists(response: APIResponse, keep: str) -> set[str]:
    return {
        name
        for name in type(response).model_fields
        if name != keep and isinstance(getattr(response, name, None), list)
    }


def _without(mapping: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in mapping.items() if name != key}
