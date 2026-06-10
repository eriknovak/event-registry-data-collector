"""File-saving helpers for the Event Registry collector.

Contains functions for creating folder structures and storing the
collected articles or events into files.
"""

import json
import logging
from pathlib import Path
from typing import Any, Iterable, IO, Optional

logger = logging.getLogger(__name__)


def create_folder_directory(path: str) -> None:
    """Creates the folder structure associated with the `path`.

    Args:
        path (str): The path to the given file.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def save_as_array(file: IO[str], articles: Iterable[Any]) -> None:
    """Save the articles as an array of objects.

    Args:
        file (IO[str]): The file object to which we wish to write.
        articles (Iterable[Any]): The iterator with all of the acquired
            articles.
    """
    json.dump([a for a in articles], file)


def save_as_separate_line(file: IO[str], articles: Iterable[Any]) -> None:
    """Saves the article objects in separate lines.

    Args:
        file (IO[str]): The file object to which we wish to write.
        articles (Iterable[Any]): The iterator with all of the acquired
            articles.
    """
    for article in articles:
        try:
            # write the article json to the file
            json.dump(article, file)
            file.write("\n")
        except (TypeError, ValueError) as error:
            logger.warning("Skipping article that could not be serialized: %s", error)
            continue


def save_result_in_file(articles: Iterable[Any], file_path: str, save_format: Optional[str] = None) -> None:
    """Saves the articles into the provided file in the given format.

    Args:
        articles (Iterable[Any]): The list of objects containing
            the article information.
        file_path (str): The path to the file the objects will be stored.
        save_format (Optional[str]): The format in which we wish to store the
            articles (Default: None). Options:
                'array' - The articles are wrapped into an array. Should not
                    be used when storing query results into the same file.
                None - The articles are stored line-by-line in the file.
    """
    # create the folder directory
    create_folder_directory(file_path)
    # store the events
    with open(file_path, "a") as f:
        if save_format == "array":
            save_as_array(f, articles)
        else:
            save_as_separate_line(f, articles)
