"""Helpers for loading and manipulating Event Registry complex queries.

The complex query format is Event Registry's advanced query language:
a JSON object with a ``$query`` condition tree built from ``$and``,
``$or`` and ``$not`` operators, and an optional ``$filter`` object. See
https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language.
"""

import json
import os
from typing import Any, Dict


def wrap_query(query: Dict[str, Any]) -> Dict[str, Any]:
    """Wraps a bare query object into the full ``$query`` form.

    Args:
        query (Dict[str, Any]): Either a full complex query (containing the
            ``$query`` key) or a bare condition object.

    Returns:
        Dict[str, Any]: The query in the full ``{"$query": ...}`` form.
    """
    if "$query" in query:
        return query
    return {"$query": query}


def inject_date_start(query: Dict[str, Any], date_start: str) -> Dict[str, Any]:
    """Returns a copy of the query constrained to dates >= `date_start`.

    The original ``$query`` condition is AND-ed with a ``dateStart``
    condition, which is valid regardless of the query nesting. Other
    top-level keys (e.g. ``$filter``) are preserved.

    Args:
        query (Dict[str, Any]): The complex query in the full ``$query`` form.
        date_start (str): The start date in the YYYY-MM-DD format.

    Returns:
        Dict[str, Any]: A new query dict with the injected date condition.

    Raises:
        ValueError: If the query is not in the full ``$query`` form.
    """
    if "$query" not in query:
        raise ValueError("inject_date_start: query must be in the full {'$query': ...} form")
    return {
        **query,
        "$query": {"$and": [query["$query"], {"dateStart": date_start}]},
    }


def load_query_file(path: str) -> Dict[str, Any]:
    """Loads and normalizes a complex query from a JSON file.

    Args:
        path (str): The path to the JSON query file.

    Returns:
        Dict[str, Any]: The query in the full ``{"$query": ...}`` form.

    Raises:
        ValueError: If the file does not exist, is not valid JSON, or does
            not contain a JSON object.
    """
    if not os.path.isfile(path):
        raise ValueError(f"Query file not found: {path}")
    with open(path) as in_file:
        try:
            query = json.load(in_file)
        except json.JSONDecodeError as error:
            raise ValueError(f"Query file is not valid JSON: {path} ({error})") from error
    if not isinstance(query, dict):
        raise ValueError(f"Query file must contain a JSON object: {path}")
    return wrap_query(query)
