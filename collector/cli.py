"""Command line interface for the Event Registry collector.

Parses the command line arguments and executes the selected
Event Registry query.
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

from collector.client import EventRegistryCollector
from collector.query import load_query_file

logger = logging.getLogger(__name__)

# the flags that define the query and conflict with --query_file
QUERY_FLAGS = ("keywords", "concepts", "categories", "sources", "languages", "date_start", "date_end")


def format_label(item: Dict[str, Any]) -> str:
    """Extracts a display label from a suggestion item.

    Args:
        item (Dict[str, Any]): A suggestion returned by the ER suggest API.

    Returns:
        str: The label in English (or the first available language), the
            source title, or an empty string.
    """
    label = item.get("label")
    if label is None:
        label = item.get("title", "")
    if isinstance(label, dict):
        return label.get("eng") or next(iter(label.values()), "")
    return str(label)


def render_suggestions(items: List[Dict[str, Any]]) -> str:
    """Renders the suggestion items as an aligned text table.

    Args:
        items (List[Dict[str, Any]]): The suggestions returned by the ER
            suggest API.

    Returns:
        str: The table with index, type, label and URI columns, or a
            message if there are no suggestions.
    """
    if not items:
        return "No suggestions found. Try a different prefix or, for concepts, the --types option."
    header = ("#", "TYPE", "LABEL", "URI")
    rows = [(str(i), item.get("type", "-"), format_label(item), item.get("uri", "")) for i, item in enumerate(items, 1)]
    widths = [max(len(row[col]) for row in [header] + rows) for col in range(4)]
    lines = ["  ".join(value.ljust(width) for value, width in zip(row, widths)) for row in [header] + rows]
    return "\n".join(lines)


def get_conflicting_flags(args: argparse.Namespace) -> List[str]:
    """Returns the query flags that were set and conflict with --query_file.

    Args:
        args (argparse.Namespace): The parsed command line arguments.

    Returns:
        List[str]: The names of the conflicting flags.
    """
    return [flag for flag in QUERY_FLAGS if getattr(args, flag, None)]


def run_suggest(er: EventRegistryCollector, args: argparse.Namespace) -> None:
    """Executes the suggest action and prints the results.

    Args:
        er (EventRegistryCollector): The initialized collector.
        args (argparse.Namespace): The parsed command line arguments.
    """
    types = [t.strip() for t in args.types.split(",")] if args.types else None
    if args.suggest_type == "concepts":
        items = er.suggest_concepts(args.prefix, types=types, lang=args.lang, count=args.count)
    elif args.suggest_type == "categories":
        items = er.suggest_categories(args.prefix, count=args.count)
    else:
        items = er.suggest_sources(args.prefix, count=args.count)

    if args.output_format == "json":
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(render_suggestions(items))


def create_argparser() -> argparse.ArgumentParser:
    """Creates the command line argument parser.

    Returns:
        argparse.ArgumentParser: The argument parser with all of the
            supported subcommands.
    """
    argparser = argparse.ArgumentParser(description="Service for retrieving event registry articles")

    subparsers = argparser.add_subparsers(help="command")

    ###################################
    # Articles Query
    ###################################

    subparser = subparsers.add_parser("articles", help="Collects the articles based on some parameters")
    subparser.set_defaults(action="articles")

    subparser.add_argument(
        "--max_repeat_request",
        type=int,
        default=-1,
        help="The maximum number of repeated requests",
    )
    subparser.add_argument(
        "--query_file",
        type=str,
        default=None,
        help="The path to a JSON file with a complex query in the ER advanced query language. "
        "Cannot be combined with the keywords/concepts/categories/sources/languages/date flags",
    )

    # query related attributes
    subparser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="The comma separated keywords the articles should contain",
    )
    subparser.add_argument(
        "--concepts",
        type=str,
        default=None,
        help="The comma separated concepts the articles should be associated with",
    )
    subparser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="The comma separated categories of the collected articles",
    )
    subparser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="The comma separated media sources that published the articles",
    )
    subparser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="The comma separated languages of the articles",
    )
    subparser.add_argument("--date_start", type=str, default=None, help="The start date of the articles")
    subparser.add_argument("--date_end", type=str, default=None, help="The end date of the articles")
    # data retrieving attributes
    subparser.add_argument("--sort_by", type=str, default="date", help="The sort order of articles")
    subparser.add_argument("--sort_by_asc", type=bool, default=True, help="The direction of the sort")
    subparser.add_argument("--max_items", type=int, default=-1, help="The number of articles to collect")
    # data storing values
    subparser.add_argument(
        "--save_to_file",
        type=str,
        default=None,
        help="The path to the file to store the articles",
    )
    subparser.add_argument(
        "--save_format",
        type=str,
        default=None,
        help="The format in which to store the articles",
    )

    subparser.add_argument(
        "--verbose",
        type=bool,
        default=False,
        help="If true, output the query parameters retrieved by ER",
    )

    ###################################
    # Events Query
    ###################################

    subparser = subparsers.add_parser("events", help="Collects the events based on some parameters")
    subparser.set_defaults(action="events")

    subparser.add_argument(
        "--max_repeat_request",
        type=int,
        default=-1,
        help="The maximum number of repeated requests",
    )
    subparser.add_argument(
        "--query_file",
        type=str,
        default=None,
        help="The path to a JSON file with a complex query in the ER advanced query language. "
        "Cannot be combined with the keywords/concepts/categories/sources/languages/date flags",
    )

    # query related attributes
    subparser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="The comma separated keywords the events should contain",
    )
    subparser.add_argument(
        "--concepts",
        type=str,
        default=None,
        help="The comma separated concepts the events should be associated with",
    )
    subparser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="The comma separated categories of the collected events",
    )
    subparser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="The comma separated media sources that published the events",
    )
    subparser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="The comma separated languages of the events",
    )
    subparser.add_argument("--date_start", type=str, default=None, help="The start date of the events")
    subparser.add_argument("--date_end", type=str, default=None, help="The end date of the events")
    # data retrieving attributes
    subparser.add_argument("--sort_by", type=str, default="date", help="The sort order of events")
    subparser.add_argument("--sort_by_asc", type=bool, default=True, help="The direction of the sort")
    subparser.add_argument("--max_items", type=int, default=-1, help="The number of events to collect")
    # data storing values
    subparser.add_argument(
        "--save_to_file",
        type=str,
        default=None,
        help="The path to the file to store the events",
    )
    subparser.add_argument(
        "--save_format",
        type=str,
        default=None,
        help="The format in which to store the events",
    )

    subparser.add_argument(
        "--verbose",
        type=bool,
        default=False,
        help="If true, output the query parameters retrieved by ER",
    )

    ###################################
    # Event Query
    ###################################

    subparser = subparsers.add_parser("event", help="Collects the events based on some parameters")
    subparser.set_defaults(action="event")

    subparser.add_argument(
        "--max_repeat_request",
        type=int,
        default=-1,
        help="The maximum number of repeated requests",
    )

    # query related attributes
    subparser.add_argument("--event_ids", type=str, default=None, help="The comma sperated event ids")
    # data storing values
    subparser.add_argument(
        "--save_to_file",
        type=str,
        default=None,
        help="The path to the file to store the events",
    )
    subparser.add_argument(
        "--save_format",
        type=str,
        default=None,
        help="The format in which to store the events",
    )

    ###################################
    # Event Articles Query
    ###################################

    subparser = subparsers.add_parser("event_articles", help="Collects the event articles based on some parameters")
    subparser.set_defaults(action="event_articles")

    subparser.add_argument(
        "--max_repeat_request",
        type=int,
        default=-1,
        help="The maximum number of repeated requests",
    )

    # query related attributes
    subparser.add_argument(
        "--event_id",
        type=str,
        default=None,
        help="The event id of the event for which we wish the articles",
    )
    subparser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="The comma separated keywords the event articles should contain",
    )
    subparser.add_argument(
        "--concepts",
        type=str,
        default=None,
        help="The comma separated concepts the event articles should be associated with",
    )
    subparser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="The comma separated categories of the collected event articles",
    )
    subparser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="The comma separated media sources that published the event articles",
    )
    subparser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="The comma separated languages of the event articles",
    )
    subparser.add_argument(
        "--date_start",
        type=str,
        default=None,
        help="The start date of the event articles",
    )
    subparser.add_argument("--date_end", type=str, default=None, help="The end date of the event articles")
    # data retrieving attributes
    subparser.add_argument("--sort_by", type=str, default="rel", help="The sort order of event articles")
    subparser.add_argument("--sort_by_asc", type=bool, default=True, help="The direction of the sort")
    subparser.add_argument(
        "--max_items",
        type=int,
        default=-1,
        help="The number of event articles to collect",
    )
    # data storing values
    subparser.add_argument(
        "--save_to_file",
        type=str,
        default=None,
        help="The path to the file to store the event articles",
    )
    subparser.add_argument(
        "--save_format",
        type=str,
        default=None,
        help="The format in which to store the event articles",
    )

    subparser.add_argument(
        "--verbose",
        type=bool,
        default=False,
        help="If true, output the query parameters retrieved by ER",
    )

    ###################################
    # Event Articles List Query
    ###################################

    subparser = subparsers.add_parser(
        "event_articles_from_file",
        help="Collects the event articles from a file and based on some parameters",
    )
    subparser.set_defaults(action="event_articles_from_file")

    subparser.add_argument(
        "--max_repeat_request",
        type=int,
        default=-1,
        help="The maximum number of repeated requests",
    )

    # query related attributes
    subparser.add_argument(
        "--event_ids_file",
        type=str,
        default=None,
        help="The file which contains the event ids",
    )
    subparser.add_argument(
        "--event_file_type",
        type=str,
        default="events",
        help="The type of the event file type. Options: 'events', 'plain'",
    )
    subparser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="The comma separated keywords the event articles should contain",
    )
    subparser.add_argument(
        "--concepts",
        type=str,
        default=None,
        help="The comma separated concepts the event articles should be associated with",
    )
    subparser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="The comma separated categories of the collected event articles",
    )
    subparser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="The comma separated media sources that published the event articles",
    )
    subparser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="The comma separated languages of the event articles",
    )
    subparser.add_argument(
        "--date_start",
        type=str,
        default=None,
        help="The start date of the event articles",
    )
    subparser.add_argument("--date_end", type=str, default=None, help="The end date of the event articles")
    # data retrieving attributes
    subparser.add_argument("--sort_by", type=str, default="rel", help="The sort order of event articles")
    subparser.add_argument("--sort_by_asc", type=bool, default=True, help="The direction of the sort")
    subparser.add_argument(
        "--max_items",
        type=int,
        default=-1,
        help="The number of event articles to collect",
    )
    # data storing values
    subparser.add_argument(
        "--save_to_file",
        type=str,
        default=None,
        help="The path to the folder to store the event articles files",
    )
    subparser.add_argument(
        "--save_format",
        type=str,
        default=None,
        help="The format in which to store the event articles",
    )

    subparser.add_argument(
        "--verbose",
        type=bool,
        default=False,
        help="If true, output the query parameters retrieved by ER",
    )

    ###################################
    # Suggest Query
    ###################################

    subparser = subparsers.add_parser("suggest", help="Suggests concept/category/source URIs for a search prefix")
    subparser.set_defaults(action="suggest")

    subparser.add_argument(
        "suggest_type",
        choices=["concepts", "categories", "sources"],
        help="The type of suggestions to retrieve",
    )
    subparser.add_argument("prefix", type=str, help="The text the suggestions should match")
    subparser.add_argument(
        "--types",
        type=str,
        default=None,
        help="The comma separated concept types (concepts only). Options: person, loc, org, wiki, entities, concepts",
    )
    subparser.add_argument("--lang", type=str, default="eng", help="The language of the prefix (concepts only)")
    subparser.add_argument("--count", type=int, default=20, help="The number of suggestions to return")
    subparser.add_argument(
        "--format",
        dest="output_format",
        choices=["table", "json"],
        default="table",
        help="The output format of the suggestions",
    )

    return argparser


def main() -> None:
    """Parses the command line arguments and executes the selected query.

    Raises:
        SystemExit: If the API_KEY environment variable is missing or empty.
    """
    # configure the logging output
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # load the environment variables
    load_dotenv()

    # parse command line arguments
    argparser = create_argparser()

    try:
        # parse the arguments and call whatever function was selected
        args = argparser.parse_args()

        # event registry API values
        max_repeat_request = getattr(args, "max_repeat_request", -1)

        # query related attributes
        keywords = (
            [k.strip() for k in args.keywords.split(",")] if hasattr(args, "keywords") and args.keywords else None
        )
        concepts = (
            [c.strip() for c in args.concepts.split(",")] if hasattr(args, "concepts") and args.concepts else None
        )
        categories = (
            [c.strip() for c in args.categories.split(",")] if hasattr(args, "categories") and args.categories else None
        )
        sources = [s.strip() for s in args.sources.split(",")] if hasattr(args, "sources") and args.sources else None
        languages = (
            [lang.strip() for lang in args.languages.split(",")]
            if hasattr(args, "languages") and args.languages
            else None
        )
        date_start = args.date_start if hasattr(args, "date_start") and args.date_start else None
        date_end = args.date_end if hasattr(args, "date_end") and args.date_end else None
        # data retrieving attributes
        sort_by = args.sort_by if hasattr(args, "sort_by") and args.sort_by else None
        sort_by_asc = (
            args.sort_by_asc in [True, "True", "true", "1", "t", "y"]
            if hasattr(args, "sort_by_asc") and args.sort_by_asc
            else None
        )
        max_items = args.max_items if hasattr(args, "max_items") and args.max_items else None
        # data storing values
        save_to_file = args.save_to_file if hasattr(args, "save_to_file") and args.save_to_file else None
        save_format = args.save_format if hasattr(args, "save_format") and args.save_format else None

        verbose = args.verbose if hasattr(args, "verbose") and args.verbose else None

        if verbose:
            # output additional debug information
            logging.getLogger().setLevel(logging.DEBUG)

        # load the complex query file if provided
        query = None
        query_file = getattr(args, "query_file", None)
        if query_file:
            conflicting = get_conflicting_flags(args)
            if conflicting:
                logger.error(
                    "--query_file cannot be combined with: %s",
                    ", ".join("--" + flag for flag in conflicting),
                )
                sys.exit(1)
            try:
                query = load_query_file(query_file)
            except ValueError as error:
                logger.error(str(error))
                sys.exit(1)

        # validate the API key before initializing the collector
        api_key = os.getenv("API_KEY")
        if not api_key:
            logger.error("API_KEY is missing or empty. Set it in the environment or in the .env file.")
            sys.exit(1)

        # initialize and execute query
        er = EventRegistryCollector(api_key=api_key, max_repeat_request=max_repeat_request)

        if args.action == "suggest":
            run_suggest(er, args)
            return

        if args.action == "articles":
            # execute the articles query
            er.get_articles(
                keywords=keywords,
                concepts=concepts,
                categories=categories,
                sources=sources,
                languages=languages,
                date_start=date_start,
                date_end=date_end,
                sort_by=sort_by,
                sort_by_asc=sort_by_asc,
                max_items=max_items,
                save_to_file=save_to_file,
                save_format=save_format,
                verbose=verbose,
                query=query,
            )

        elif args.action == "events":
            # execute the events query
            er.get_events(
                keywords=keywords,
                concepts=concepts,
                categories=categories,
                sources=sources,
                languages=languages,
                date_start=date_start,
                date_end=date_end,
                sort_by=sort_by,
                sort_by_asc=sort_by_asc,
                max_items=max_items,
                save_to_file=save_to_file,
                save_format=save_format,
                verbose=verbose,
                query=query,
            )

        elif args.action == "event":
            if not args.event_ids:
                raise Exception("Attribute event_ids must be specified")

            # get query specific information
            event_ids = args.event_ids.split(",")
            er.get_event(event_ids=event_ids, save_to_file=save_to_file, save_format=save_format)

        elif args.action == "event_articles":
            # get query specific information
            event_id = args.event_id if args.event_id else None
            # execute the events query
            er.get_event_articles(
                event_id,
                keywords=keywords,
                concepts=concepts,
                categories=categories,
                sources=sources,
                languages=languages,
                date_start=date_start,
                date_end=date_end,
                sort_by=sort_by,
                sort_by_asc=sort_by_asc,
                max_items=max_items,
                save_to_file=save_to_file,
                save_format=save_format,
                verbose=verbose,
            )

        elif args.action == "event_articles_from_file":
            # get query specific information
            event_ids_file = args.event_ids_file if args.event_ids_file else None
            event_file_type = args.event_file_type if args.event_file_type else None

            # execute the events query
            er.get_event_articles_from_file(
                event_ids_file,
                event_file_type=event_file_type,
                keywords=keywords,
                concepts=concepts,
                categories=categories,
                sources=sources,
                languages=languages,
                date_start=date_start,
                date_end=date_end,
                sort_by=sort_by,
                sort_by_asc=sort_by_asc,
                max_items=max_items,
                save_to_folder=save_to_file,
                save_format=save_format,
                verbose=verbose,
            )

        else:
            raise Exception("Argument command is unknown: {}".format(args.command))
    except KeyboardInterrupt:
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
