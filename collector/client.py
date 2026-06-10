"""The Event Registry API classes.

Retrieves articles, events and other news data from the Event Registry
service. Contains additional classes used for retrieving and processing.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Union

import eventregistry as ER

from collector.query import inject_date_start
from collector.storage import save_result_in_file

logger = logging.getLogger(__name__)


def get_items(obj: Optional[ER.QueryItems]) -> Optional[List[str]]:
    """Gets the items stored in the query items object.

    Args:
        obj (Optional[ER.QueryItems]): The query items object.

    Returns:
        Optional[List[str]]: The items stored in the object, or the
            object itself if it is falsy.
    """
    return obj.getItems() if obj else obj


def print_query_params(params: Dict[str, Any]) -> None:
    """Logs the event registry query parameters.

    Args:
        params (Dict[str, Any]): The dictionary containing the query
            parameters (keywords, concepts, categories, sources,
            date_start, date_end, languages).
    """
    keywords = get_items(params["keywords"])
    concepts = get_items(params["concepts"])
    categories = get_items(params["categories"])
    sources = get_items(params["sources"])
    date_start = params["date_start"]
    date_end = params["date_end"]
    languages = params["languages"]

    message = f"""
        EVENT REGISTRY QUERY PARAMETERS
            keywords:   {keywords}
            concepts:   {concepts}
            categories: {categories}
            sources:    {sources}
            date_start: {date_start}
            date_end:   {date_end}
            languages:  {languages}
    """

    logger.info(message)


def is_concept_uri(value: str) -> bool:
    """Checks whether the value is already a concept URI.

    Args:
        value (str): The concept name or URI.

    Returns:
        bool: True if the value is a URI (starts with http:// or https://).
    """
    return value.startswith(("http://", "https://"))


def is_category_uri(value: str) -> bool:
    """Checks whether the value is already a category URI.

    Args:
        value (str): The category name or URI.

    Returns:
        bool: True if the value is a URI (starts with dmoz/ or news/).
    """
    return value.startswith(("dmoz/", "news/"))


def is_source_uri(value: str) -> bool:
    """Checks whether the value is already a source URI.

    Args:
        value (str): The source name or URI.

    Returns:
        bool: True if the value looks like a domain (contains a dot and is not an HTTP URL).
    """
    return "." in value and not value.startswith(("http://", "https://"))


def get_last_date(file_path: Optional[str], date_field: str) -> Optional[str]:
    """Reads the date of the last stored item in a JSONL file.

    Args:
        file_path (Optional[str]): The path of the JSONL file.
        date_field (str): The attribute holding the item date (e.g. 'date'
            for articles, 'eventDate' for events).

    Returns:
        Optional[str]: The date of the last item, or None if the file does
            not exist or is empty.
    """
    if not (file_path and os.path.isfile(file_path)):
        return None
    with open(file_path) as in_file:
        lines = in_file.readlines()
    if len(lines) == 0:
        return None
    return json.loads(lines[-1]).get(date_field)


@dataclass(frozen=True)
class URI:
    """The keyword and concept pair used in the event registry collector.

    Attributes:
        keyword (str): The source keyword for the concept.
        uri (str): The wikipedia concept URI associated with the
            source keyword.
    """

    keyword: str
    uri: str

    def get_keyword(self) -> str:
        """Gets the keyword value.

        Returns:
            str: The source keyword.
        """
        return self.keyword

    def get_uri(self) -> str:
        """Gets the wikipedia concept.

        Returns:
            str: The wikipedia concept URI.
        """
        return self.uri


class EventRegistryCollector:
    """Collects articles and events from the Event Registry service.

    Attributes:
        MAX_EVENT_REQUESTS (int): The maximum number of event ids that
            can be requested in a single query.
    """

    def __init__(self, api_key: str, max_repeat_request: int = -1):
        """Initializes the event registry collector.

        Args:
            api_key (str): The Event Registry API key.
            max_repeat_request (int): The number of maximum
                requests that can be repeated if something
                goes wrong. If -1, repeat indefinately
                (Default: -1).
        """
        # initialize the event registry instance
        self._er = ER.EventRegistry(apiKey=api_key, repeatFailedRequestCount=max_repeat_request)
        self.MAX_EVENT_REQUESTS = 50

    def get_concepts(self, concepts: List[str]) -> List[URI]:
        """Get the list of event registry concepts.

        Values that are already URIs are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            concepts (List[str]): The list of concept names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given concept URIs.
        """
        uris = []
        for k in concepts:
            if is_concept_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getConceptUri(k)
            logger.warning(
                "resolved %r -> %s (use 'collect suggest concepts' to pick explicitly)", k, uri
            )
            uris.append(URI(k, uri))
        return uris

    def get_categories(self, categories: List[str]) -> List[URI]:
        """Get the list of event registry categories.

        Values that are already URIs are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            categories (List[str]): The list of category names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given category URIs.
        """
        uris = []
        for k in categories:
            if is_category_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getCategoryUri(k)
            logger.warning(
                "resolved %r -> %s (use 'collect suggest categories' to pick explicitly)", k, uri
            )
            uris.append(URI(k, uri))
        return uris

    def get_sources(self, sources: List[str]) -> List[URI]:
        """Get the list of source uris.

        Values that look like domains are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            sources (List[str]): The list of source names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given source URIs.
        """
        uris = []
        for k in sources:
            if is_source_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getSourceUri(k)
            logger.warning(
                "resolved %r -> %s (use 'collect suggest sources' to pick explicitly)", k, uri
            )
            uris.append(URI(k, uri))
        return uris

    def suggest_concepts(
        self,
        prefix: str,
        types: Optional[List[str]] = None,
        lang: str = "eng",
        count: int = 20,
    ) -> List[Dict[str, Any]]:
        """Gets the ranked concept suggestions for the given prefix.

        Args:
            prefix (str): The text the concept should match.
            types (Optional[List[str]]): The concept types to return. Valid
                values: person, loc, org, wiki, entities (person + loc + org),
                concepts (entities + wiki). If None, the 'concepts' source is
                used, which covers all types (Default: None).
            lang (str): The language of the prefix (Default: 'eng').
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked concept candidates with their
                uri, type and label.
        """
        return self._er.suggestConcepts(
            prefix, sources=types or ["concepts"], lang=lang, count=count
        )

    def suggest_categories(self, prefix: str, count: int = 20) -> List[Dict[str, Any]]:
        """Gets the ranked category suggestions for the given prefix.

        Args:
            prefix (str): The text the category name should match.
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked category candidates with their uri.
        """
        return self._er.suggestCategories(prefix, count=count)

    def suggest_sources(self, prefix: str, count: int = 20) -> List[Dict[str, Any]]:
        """Gets the ranked news source suggestions for the given prefix.

        Args:
            prefix (str): The text the source name or uri should match.
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked source candidates with their
                uri and title.
        """
        return self._er.suggestNewsSources(prefix, count=count)

    def get_articles(
        self,
        keywords: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        sort_by: str = "date",
        sort_by_asc: bool = False,
        max_items: int = -1,
        save_to_file: Optional[str] = None,
        save_format: Optional[str] = None,
        verbose: bool = False,
        query: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """Get the event registry articles.

        Args:
            keywords (Optional[List[str]]): The list of keywords the articles
                should contain (Default: None).
            concepts (Optional[List[str]]): The list of concepts the articles
                should contain (Default: None).
            categories (Optional[List[str]]): The list of categories the articles
                should be in (Default: None).
            sources (Optional[List[str]]): The list of sources from which to
                retrieve the articles (Default: None).
            languages (Optional[List[str]]): The list of languages the articles
                should be written in (Default: None).
            date_start (Optional[str]): The start date from which the articles
                should be acquired. If None, it starts from the first
                date supported by Event Registry (Default: None).
            date_end (Optional[str]): The end date until which the articles
                should be acquired. If None, it ends at the day of
                collecting (Default: None).
            sort_by (str): The sorting attribute (Default: 'date'). See
                https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles.
            sort_by_asc (bool): If the documents should be sorted in
                ascending (True) or descending order (False) (Default: False).
            max_items (int): The maximum number of articles to retrieve,
                where -1 means return all matching articles (Default: -1).
            save_to_file (Optional[str]): The path to which we wish to store the articles.
                If None, the articles are not stored. In addition, if the same
                file is used for multiple queries, the new articles will be
                appended to the existing ones (Default: None).
            save_format (Optional[str]): The format in which the articles are stored. (Default: None)
                Options:
                    'array' - The articles are wrapped into an array. Should not
                        be used when storing query results into the same file.
                    None - The articles are stored line-by-line in the file.
            verbose (bool): If true, output the query parameters retrieved by ER (Default: False).
            query (Optional[Dict[str, Any]]): A complex query in Event
                Registry's advanced query language (the full
                {"$query": ...} form). Cannot be combined with the flat
                query parameters (keywords, concepts, categories, sources,
                languages, date_start, date_end) (Default: None).

        Returns:
            Iterator[Any]: The iterator which goes through all retrieved articles.
        """
        if query is not None:
            flat_params = [keywords, concepts, categories, sources, languages, date_start, date_end]
            if any(p is not None for p in flat_params):
                raise ValueError("get_articles: 'query' cannot be combined with the flat query parameters")

            last_date = get_last_date(save_to_file, "date")
            if last_date:
                query = inject_date_start(query, last_date)
                logger.info("Resuming collection from %s (last date in %s)", last_date, save_to_file)

            q = ER.QueryArticlesIter.initWithComplexQuery(query)
        else:
            # setup the event registry parameters
            er_keywords = ER.QueryItems.AND(keywords) if keywords else None
            er_concepts = ER.QueryItems.AND([c.uri for c in self.get_concepts(concepts)]) if concepts else None
            er_categories = ER.QueryItems.AND([c.uri for c in self.get_categories(categories)]) if categories else None
            er_sources = ER.QueryItems.OR([c.uri for c in self.get_sources(sources)]) if sources else None
            er_lang = ER.QueryItems.OR(languages) if languages else None

            # when saving to file check the last date and use it as start date
            last_date = get_last_date(save_to_file, "date")
            if last_date:
                date_start = last_date

            if verbose:
                print_query_params(
                    {
                        "keywords": er_keywords,
                        "concepts": er_concepts,
                        "categories": er_categories,
                        "sources": er_sources,
                        "date_start": date_start,
                        "date_end": date_end,
                        "languages": languages,
                    }
                )

            # creates the query articles object
            q = ER.QueryArticlesIter(
                keywords=er_keywords,
                conceptUri=er_concepts,
                categoryUri=er_categories,
                sourceUri=er_sources,
                dateStart=date_start,
                dateEnd=date_end,
                lang=er_lang,
            )

        # execute the query and return the iterator
        articles = q.execQuery(self._er, sortBy=sort_by, sortByAsc=sort_by_asc, maxItems=max_items)

        if save_to_file:
            save_result_in_file(articles, save_to_file, save_format)

        # return the articles for other use
        return articles

    def get_events(
        self,
        keywords: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        sort_by: str = "date",
        sort_by_asc: bool = False,
        max_items: int = -1,
        save_to_file: Optional[str] = None,
        save_format: Optional[str] = None,
        verbose: bool = False,
        query: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """Get the event registry events.

        Args:
            keywords (Optional[List[str]]): The list of keywords the events
                should contain (Default: None).
            concepts (Optional[List[str]]): The list of concepts the events
                should contain (Default: None).
            categories (Optional[List[str]]): The list of categories the events
                should be in (Default: None).
            sources (Optional[List[str]]): The list of sources from which to
                retrieve the events (Default: None).
            languages (Optional[List[str]]): The list of languages the events
                should be written in (Default: None).
            date_start (Optional[str]): The start date from which the events
                should be acquired. If None, it starts from the first
                date supported by Event Registry (Default: None).
            date_end (Optional[str]): The end date until which the events
                should be acquired. If None, it ends at the day of
                collecting (Default: None).
            sort_by (str): The sorting attribute (Default: 'date'). See
                https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles.
            sort_by_asc (bool): If the documents should be sorted in
                ascending (True) or descending order (False) (Default: False).
            max_items (int): The maximum number of events to retrieve,
                where -1 means return all matching events (Default: -1).
            save_to_file (Optional[str]): The path to which we wish to store the events.
                If None, the events are not stored. In addition, if the same
                file is used for multiple queries, the new events will be
                appended to the existing ones (Default: None).
            save_format (Optional[str]): The format in which the events are stored. (Default: None)
                Options:
                    'array' - The events are wrapped into an array. Should not
                        be used when storing query results into the same file.
                    None - The events are stored line-by-line in the file.
            verbose (bool): If true, output the query parameters retrieved by ER (Default: False).
            query (Optional[Dict[str, Any]]): A complex query in Event
                Registry's advanced query language (the full
                {"$query": ...} form). Cannot be combined with the flat
                query parameters (keywords, concepts, categories, sources,
                languages, date_start, date_end) (Default: None).

        Returns:
            Iterator[Any]: The iterator which goes through all retrieved events.
        """
        if query is not None:
            flat_params = [keywords, concepts, categories, sources, languages, date_start, date_end]
            if any(p is not None for p in flat_params):
                raise ValueError("get_events: 'query' cannot be combined with the flat query parameters")

            last_date = get_last_date(save_to_file, "eventDate")
            if last_date:
                query = inject_date_start(query, last_date)
                logger.info("Resuming collection from %s (last date in %s)", last_date, save_to_file)

            q = ER.QueryEventsIter.initWithComplexQuery(query)
        else:
            # setup the event registry parameters
            er_keywords = ER.QueryItems.AND(keywords) if keywords else None
            er_concepts = ER.QueryItems.AND([c.uri for c in self.get_concepts(concepts)]) if concepts else None
            er_categories = ER.QueryItems.AND([c.uri for c in self.get_categories(categories)]) if categories else None
            er_sources = ER.QueryItems.OR([c.uri for c in self.get_sources(sources)]) if sources else None
            er_lang = ER.QueryItems.OR(languages) if languages else None

            # when saving to file check the last date and use it as start date
            last_date = get_last_date(save_to_file, "eventDate")
            if last_date:
                date_start = last_date

            if verbose:
                print_query_params(
                    {
                        "keywords": er_keywords,
                        "concepts": er_concepts,
                        "categories": er_categories,
                        "sources": er_sources,
                        "date_start": date_start,
                        "date_end": date_end,
                        "languages": languages,
                    }
                )

            # creates the query events object
            q = ER.QueryEventsIter(
                keywords=er_keywords,
                conceptUri=er_concepts,
                categoryUri=er_categories,
                sourceUri=er_sources,
                dateStart=date_start,
                dateEnd=date_end,
                lang=er_lang,
            )

        # execute the query and return the iterator
        events = q.execQuery(self._er, sortBy=sort_by, sortByAsc=sort_by_asc, maxItems=max_items)

        if save_to_file:
            # saves the events into the file
            save_result_in_file(events, save_to_file, save_format)

        # return the events for other use
        return events

    def get_event(
        self,
        event_ids: Union[List[str], str],
        save_to_file: Optional[str] = None,
        save_format: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get the events with the provided event IDs.

        Args:
            event_ids (Union[List[str], str]): The list of event ids. Can be a single
                string or a list of strings.
            save_to_file (Optional[str]): The path to which we wish to store the events.
                If None, the events are not stored. In addition, if the same
                file is used for multiple queries, the new events will be
                appended to the existing ones (Default: None).
            save_format (Optional[str]): The format in which the events are stored. (Default: None)
                Options:
                    'array' - The events are wrapped into an array. Should not
                        be used when storing query results into the same file.
                    None - The events are stored line-by-line in the file.

        Returns:
            List[Dict[str, Any]]: The list with the retrieved events.

        Raises:
            Exception: If `event_ids` is not a list or a string.
        """
        query_queue = []
        if type(event_ids) is list:
            # split the list into chunks of at most 50 event ids
            chunk_number = len(event_ids) % self.MAX_EVENT_REQUESTS
            for i in range(chunk_number + 1):
                start = self.MAX_EVENT_REQUESTS * i
                end = self.MAX_EVENT_REQUESTS * (i + 1)
                query_queue.append(ER.QueryEvent(event_ids[start:end]))
        elif type(event_ids) is str:
            query_queue.append(ER.QueryEvent(event_ids))
        else:
            raise Exception("get_event: event_ids is not a list or a string")

        # go through the query queue and execute the requests
        events = []
        for query in query_queue:
            response = self._er.execQuery(query)
            events.extend([obj["info"] for obj in list(response.values()) if "info" in obj])

        if save_to_file:
            save_result_in_file(events, save_to_file, save_format)

        # return the events for other use
        return events

    def get_event_articles(
        self,
        event_id: str,
        keywords: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        sort_by: str = "date",
        sort_by_asc: bool = False,
        max_items: int = -1,
        save_to_file: Optional[str] = None,
        save_format: Optional[str] = None,
        verbose: bool = False,
    ) -> Iterator[Any]:
        """Get the articles of a certain event.

        Args:
            event_id (str): The event id from which we get the
                news articles within the event.
            keywords (Optional[List[str]]): The list of keywords the articles
                should contain (Default: None).
            concepts (Optional[List[str]]): The list of concepts the articles
                should contain (Default: None).
            categories (Optional[List[str]]): The list of categories the articles
                should be in (Default: None).
            sources (Optional[List[str]]): The list of sources from which to
                retrieve the articles (Default: None).
            languages (Optional[List[str]]): The list of languages the articles
                should be written in (Default: None).
            date_start (Optional[str]): The start date from which the articles
                should be acquired. If None, it starts from the first
                date supported by Event Registry (Default: None).
            date_end (Optional[str]): The end date until which the articles
                should be acquired. If None, it ends at the day of
                collecting (Default: None).
            sort_by (str): The sorting attribute (Default: 'date'). See
                https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles.
            sort_by_asc (bool): If the documents should be sorted in
                ascending (True) or descending order (False) (Default: False).
            max_items (int): The maximum number of articles to retrieve,
                where -1 means return all matching articles (Default: -1).
            save_to_file (Optional[str]): The path to which we wish to store the articles.
                If None, the articles are not stored. In addition, if the same
                file is used for multiple queries, the new articles will be
                appended to the existing ones (Default: None).
            save_format (Optional[str]): The format in which the articles are stored. (Default: None)
                Options:
                    'array' - The articles are wrapped into an array. Should not
                        be used when storing query results into the same file.
                    None - The articles are stored line-by-line in the file.
            verbose (bool): If true, output the query parameters retrieved by ER (Default: False).

        Returns:
            Iterator[Any]: The iterator which goes through all retrieved articles.
        """
        # setup the event registry parameters
        er_keywords = ER.QueryItems.AND(keywords) if keywords else None
        er_concepts = ER.QueryItems.AND([c.uri for c in self.get_concepts(concepts)]) if concepts else None
        er_categories = ER.QueryItems.AND([c.uri for c in self.get_categories(categories)]) if categories else None
        er_sources = ER.QueryItems.OR([c.uri for c in self.get_sources(sources)]) if sources else None
        er_lang = ER.QueryItems.OR(languages) if languages else None

        if verbose:
            print_query_params(
                {
                    "keywords": er_keywords,
                    "concepts": er_concepts,
                    "categories": er_categories,
                    "sources": er_sources,
                    "date_start": date_start,
                    "date_end": date_end,
                    "languages": languages,
                }
            )

        # creates the query event articles object
        q = ER.QueryEventArticlesIter(
            event_id,
            keywords=er_keywords,
            conceptUri=er_concepts,
            categoryUri=er_categories,
            sourceUri=er_sources,
            dateStart=date_start,
            dateEnd=date_end,
            lang=er_lang,
        )

        # execute the query and return the iterator
        articles = q.execQuery(self._er, sortBy=sort_by, sortByAsc=sort_by_asc, maxItems=max_items)

        if save_to_file:
            # saves the articles into the file
            save_result_in_file(articles, save_to_file, save_format)

        # return the articles for other use
        return articles

    def get_event_articles_from_file(
        self,
        event_ids_file: str,
        event_file_type: str = "events",
        keywords: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        sort_by: str = "date",
        sort_by_asc: bool = False,
        max_items: int = -1,
        save_to_folder: Optional[str] = None,
        save_format: Optional[str] = None,
        verbose: bool = False,
    ) -> List[Dict[str, Any]]:
        """Gets the event articles from a list of event ids stored in a file.

        The event ids are read from a separate file and the articles are
        stored in their own event json file.

        Args:
            event_ids_file (str): The event ids file path containing
                the event ids.
            event_file_type (str): The event file type (Default: 'events'). Options:
                - 'plain', where each line of the file contains a single event id
                - 'events', where each line of the file contains an event registry event object
                    with the 'url' attribute (used as the event id)
            keywords (Optional[List[str]]): The list of keywords the articles
                should contain (Default: None).
            concepts (Optional[List[str]]): The list of concepts the articles
                should contain (Default: None).
            categories (Optional[List[str]]): The list of categories the articles
                should be in (Default: None).
            sources (Optional[List[str]]): The list of sources from which to
                retrieve the articles (Default: None).
            languages (Optional[List[str]]): The list of languages the articles
                should be written in (Default: None).
            date_start (Optional[str]): The start date from which the articles
                should be acquired. If None, it starts from the first
                date supported by Event Registry (Default: None).
            date_end (Optional[str]): The end date until which the articles
                should be acquired. If None, it ends at the day of
                collecting (Default: None).
            sort_by (str): The sorting attribute (Default: 'date'). See
                https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles.
            sort_by_asc (bool): If the documents should be sorted in
                ascending (True) or descending order (False) (Default: False).
            max_items (int): The maximum number of articles to retrieve,
                where -1 means return all matching articles (Default: -1).
            save_to_folder (Optional[str]): The folder in which we wish to store the event articles.
                If None, the articles are not stored (Default: None).
            save_format (Optional[str]): The format in which the articles are stored. (Default: None)
                Options:
                    'array' - The articles are wrapped into an array.
                    None - The articles are stored line-by-line in the file.
            verbose (bool): If true, output the query parameters retrieved by ER (Default: False).

        Returns:
            List[Dict[str, Any]]: The list of event ids with their associated articles.

        Raises:
            Exception: If `event_ids_file` does not exist or is empty.
        """
        # check if the event ids file exists
        if not (event_ids_file and os.path.isfile(event_ids_file)):
            raise Exception("get_event_articles_list: event_ids_file doesn't exist")

        # open the file with the given event ids
        event_ids = []
        with open(event_ids_file, "r") as f:
            lines = f.readlines()

            if len(lines) == 0:
                raise Exception("get_event_articles_list: event_ids_file is empty")

            if event_file_type == "events":
                # the file contains whole event objects, extract only the ids
                for line in lines:
                    line = json.loads(line)
                    event_ids.append(line["uri"].strip())
            else:
                # each line of the file is a separate event id
                for line in lines:
                    event_ids.append(line.strip())

        event_articles = []

        for event_id in event_ids:
            # setup the event path
            event_path = "{}/{}.json".format(save_to_folder, event_id) if save_to_folder else None

            # get the event articles
            articles = self.get_event_articles(
                event_id,
                keywords,
                concepts,
                categories,
                sources,
                languages,
                date_start,
                date_end,
                sort_by,
                sort_by_asc,
                max_items,
                event_path,
                save_format,
                verbose,
            )

            # store the articles and the event id
            event_articles.append({"event_id": event_id, "articles": articles})

        # return the list of event articles
        return event_articles
