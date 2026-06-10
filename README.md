# Event Registry Collector

This project allows users to collect the news articles and event via the [Event Registry](https://eventregistry.org)
service from the command line. The source code is stored within the [collector](./collector) folder.

## Prerequisites

- Install Python 3.x or higher
- Create a new python environment to store the project dependencies via
  `venv` or `anaconda` (optional, but recommended)

  - venv

    ```bash
    # create a new virtual environment with the installed python
    # and save it in the ./venv folder
    python -m venv ./venv
    # on windows: activate the virtual environment
    ./venv/Scripts/activate
    # on UNIX: activate the virtual environment
    . ./venv/bin/activate
    # deativate the virtual environemtn
    deactivate
    ```

  - anaconda
    ```bash
    # create a new virtual environment with the latest python 3.x version
    conda create --name event-registry python=3
    # activate the virtual environment
    conda activate event-registry
    # deativate the virtual environemtn
    conda deactivate
    ```

- Install the python dependency modules

  ```bash
  pip install -e .
  ```

- Create a `.env` file in the root of the project and insert the event registry API key
  ```bash
  # create the .env file with the API key as the content
  echo "API_KEY={insert-er-api-key}" > .env
  ```

## Event Registry Collector Service

To run the service one must provide the following parameters.

| Name     | Optional | Description                                                                                                                                                        |
| -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| {action} | False    | The action to execute. Options: [articles](#articles), [events](#events), [suggest](#suggest), [event_articles](#event_articles), [event_articles_from_file](#event_articles_from_file) |

### <a name="articles"></a> Action: "articles"

This `{action}` is used to acquire news articles. To acquire them one can provide additional parameters.

| Name               | Optional | Description                                                                                                                                                                                                        |
| ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| max_repeat_request | True     | The maximum number of repeated requests. If the values is -1, it repeats indefinetely (Default: -1)                                                                                                                |
| query_file         | True     | The path to a JSON file containing a complex query in the Event Registry [advanced query language](https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language). Cannot be combined with the keywords, concepts, categories, sources, languages, date_start or date_end parameters (Default: None) |
| keywords           | True     | The comma separated keywords the articles should contain (Default: None)                                                                                                                                           |
| concepts           | True     | The comma separated concepts the articles should be associated with (Default: None)                                                                                                                                |
| categories         | True     | The comma separated categories of the collected articles (Default: None)                                                                                                                                           |
| sources            | True     | The comma separated media sources that published the articles (Default: None)                                                                                                                                      |
| languages          | True     | The comma separated languages of the articles (Default: None)                                                                                                                                                      |
| date_start         | True     | The start date of the articles. Format: YYYY-MM-DD (Default: None)                                                                                                                                                 |
| date_end           | True     | The end date of the articles. Format: YYYY-MM-DD (Default: None)                                                                                                                                                   |
| sort_by            | True     | The sort order of articles (Default: `'date'`)                                                                                                                                                                     |
| sort_by_asc        | True     | The direction of the sort (Default: True)                                                                                                                                                                          |
| max_items          | True     | The number of articles to collect. If its -1, then there is no limit (Default: -1)                                                                                                                                 |
| save_to_file       | True     | The path to the file to store the articles. If this parameter is provided, it checks the date of the last acquired article and replaces the date_start parameter with the date of the last article (Default: None) |
| save_format        | True     | The format in which to store the articles. If `'array'`, it stores the articles into an array of objects. Otherwise, each line consists of one article object (Default: None)                                      |
| verbose            | True     | If true, outputs the query parameters retrieved by Event Registry (Default: False)                                                                                                                                 |

An example of the `articles` action command is presented bellow.

```bash
collect articles \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_articles.json
```

### <a name="events"></a> Action: "events"

This `{action}` is used to acquire news events. To acquire them one can provide additional parameters.

| Name               | Optional | Description                                                                                                                                                                                                      |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| max_repeat_request | True     | The maximum number of repeated requests. If the values is -1, it repeats indefinetely (Default: -1)                                                                                                              |
| query_file         | True     | The path to a JSON file containing a complex query in the Event Registry [advanced query language](https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language). Cannot be combined with the keywords, concepts, categories, sources, languages, date_start or date_end parameters (Default: None) |
| keywords           | True     | The comma separated keywords the events should contain (Default: None)                                                                                                                                           |
| concepts           | True     | The comma separated concepts the events should be associated with (Default: None)                                                                                                                                |
| categories         | True     | The comma separated categories of the collected events (Default: None)                                                                                                                                           |
| sources            | True     | The comma separated media sources that published the events (Default: None)                                                                                                                                      |
| languages          | True     | The comma separated languages of the events (Default: None)                                                                                                                                                      |
| date_start         | True     | The start date of the events. Format: YYYY-MM-DD (Default: None)                                                                                                                                                 |
| date_end           | True     | The end date of the events. Format: YYYY-MM-DD (Default: None)                                                                                                                                                   |
| sort_by            | True     | The sort order of events (Default: `'date'`)                                                                                                                                                                     |
| sort_by_asc        | True     | The direction of the sort (Default: True)                                                                                                                                                                        |
| max_items          | True     | The number of events to collect. If its -1, then there is no limit (Default: -1)                                                                                                                                 |
| save_to_file       | True     | The path to the file to store the events. If this parameter is provided, it checks the date of the last acquired event and replaces the date_start parameter with the date of the last event (Default: None)     |
| save_format        | True     | The format in which to store the events. If `'array'`, it stores the events into an array of objects. Otherwise, each line consists of one event object (Default: None)                                          |
| verbose            | True     | If true, outputs the query parameters retrieved by Event Registry (Default: False)                                                                                                                               |

An example of the `events` action command is presented bellow.

```bash
collect events \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events.jsonl
```

### <a name="suggest"></a> Action: "suggest"

This `{action}` queries the Event Registry suggest API and prints the ranked candidate URIs,
so you can pick the exact concept/category/source instead of relying on automatic resolution.

| Name   | Optional | Description                                                                                             |
| ------ | -------- | --------------------------------------------------------------------------------------------------------- |
| type   | False    | The suggestion type (positional). Options: `concepts`, `categories`, `sources`                         |
| prefix | False    | The text the suggestions should match (positional)                                                      |
| types  | True     | The comma separated concept types (concepts only). Options: person, loc, org, wiki, entities, concepts |
| lang   | True     | The language of the prefix (concepts only) (Default: `'eng'`)                                           |
| count  | True     | The number of suggestions to return (Default: 20)                                                       |
| format | True     | The output format. Options: `table`, `json` (Default: `'table'`)                                        |

```bash
collect suggest concepts "luka doncic" --types=person
collect suggest categories "basketball"
collect suggest sources "delo"
```

When a query uses plain names instead of URIs, the collector resolves them automatically and
logs a warning showing the chosen URI. Use the URI directly (in the flags or in a query file)
to avoid the automatic selection.

### Complex queries with --query_file

For queries that need nested AND/OR/NOT logic, pass a JSON file in the Event Registry
advanced query language to the `articles` or `events` action:

```bash
collect events \
    --max_repeat_request=5 \
    --query_file=./queries/eu_presidency.json \
    --save_to_file=./data/eu_presidency_events.jsonl
```

The file contains a `$query` object built from `$and`/`$or`/`$not` operators (see
[queries/eu_presidency.json](./queries/eu_presidency.json) for an example). A bare query
object without the `$query` wrapper is also accepted. When `--save_to_file` points to an
existing file, the date of the last stored item is injected into the query automatically,
so repeated runs only collect new items.

### <a name="event_articles"></a> Action: "event_articles"

This `{action}` is used to acquire news articles clustered in a certain event. To acquire them one can provide additional parameters.

| Name               | Optional | Description                                                                                                                                                                         |
| ------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| max_repeat_request | True     | The maximum number of repeated requests. If the values is -1, it repeats indefinetely (Default: -1)                                                                                 |
| event_id           | False    | The id of the event for which we wish to collect the articles                                                                                                                       |
| keywords           | True     | The comma separated keywords the event articles should contain (Default: None)                                                                                                      |
| concepts           | True     | The comma separated concepts the event articles should be associated with (Default: None)                                                                                           |
| categories         | True     | The comma separated categories of the collected event articles (Default: None)                                                                                                      |
| sources            | True     | The comma separated media sources that published the event articles (Default: None)                                                                                                 |
| languages          | True     | The comma separated languages of the event articles (Default: None)                                                                                                                 |
| date_start         | True     | The start date of the event articles. Format: YYYY-MM-DD (Default: None)                                                                                                            |
| date_end           | True     | The end date of the event articles. Format: YYYY-MM-DD (Default: None)                                                                                                              |
| sort_by            | True     | The sort order of event articles (Default: `'rel'`)                                                                                                                                 |
| sort_by_asc        | True     | The direction of the sort (Default: True)                                                                                                                                           |
| max_items          | True     | The number of event articles to collect. If its -1, then there is no limit (Default: -1)                                                                                            |
| save_to_file       | True     | The path to the file to store the event articles (Default: None)                                                                                                                    |
| save_format        | True     | The format in which to store the event articles. If `'array'`, it stores the articles into an array of objects. Otherwise, each line consists of one article object (Default: None) |
| verbose            | True     | If true, outputs the query parameters retrieved by Event Registry (Default: False)                                                                                                  |

An example of the `event_articles` action command is presented bellow.

```bash
collect event_articles \
    --max_repeat_request=5 \
    --event_id=eng-2940883 \
    --max_items=10 \
    --save_to_file=./data/eng-2940883.json
```

### <a name="event_articles_from_file"></a> Action: "event_articles_from_file"

This `{action}` is used to acquire news articles of the events - where the event ids are provided in a file. With this, we can collect multiple event articles with a single command. To acquire them one can provide additional parameters.

| Name               | Optional | Description                                                                                                                                                                                                      |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| max_repeat_request | True     | The maximum number of repeated requests. If the values is -1, it repeats indefinetely (Default: -1)                                                                                                              |
| event_ids_file     | False    | The path to the file containing the event ids                                                                                                                                                                    |
| event_file_type    | True     | The type of the file. Options: 'plain' (each line of the file contains a single event id), 'events' (each line contains an event object with its event id stored in the `'uri'` attribute) (Default: `'events'`) |
| keywords           | True     | The comma separated keywords the event articles should contain (Default: None)                                                                                                                                   |
| concepts           | True     | The comma separated concepts the event articles should be associated with (Default: None)                                                                                                                        |
| categories         | True     | The comma separated categories of the collected event articles (Default: None)                                                                                                                                   |
| sources            | True     | The comma separated media sources that published the event articles (Default: None)                                                                                                                              |
| languages          | True     | The comma separated languages of the event articles (Default: None)                                                                                                                                              |
| date_start         | True     | The start date of the event articles. Format: YYYY-MM-DD (Default: None)                                                                                                                                         |
| date_end           | True     | The end date of the event articles. Format: YYYY-MM-DD (Default: None)                                                                                                                                           |
| sort_by            | True     | The sort order of event articles (Default: `'rel'`)                                                                                                                                                              |
| sort_by_asc        | True     | The direction of the sort (Default: True)                                                                                                                                                                        |
| max_items          | True     | The number of event articles to collect. If its -1, then there is no limit (Default: -1)                                                                                                                         |
| save_to_file       | True     | The path to the **folder** to store the event articles (Default: None)                                                                                                                                           |
| save_format        | True     | The format in which to store the event articles. If `'array'`, it stores the articles into an array of objects. Otherwise, each line consists of one article object (Default: None)                              |
| verbose            | True     | If true, outputs the query parameters retrieved by Event Registry (Default: False)                                                                                                                               |

An example of the `event_articles_from_file` action command is presented bellow.

```bash
# first collect some events of a certain topic
collect events \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events.jsonl

# afterwards leverage the collected events for acquiring the event articles
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/barrack_trump_events.jsonl \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events
```
