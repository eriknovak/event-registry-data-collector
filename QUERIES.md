# Query Examples

This file contains examples of Event Registry queries. Feel free to change them
to fit your needs.

### Events about Luka Dončič (basketball player)

```bash
# get the events mentioning Luka Dončić (basketball player)
collect events \
    --max_repeat_request=5 \
    --concepts="Luka Dončić" \
    --languages=eng,slv \
    --date_start=2021-01-01 \
    --save_to_file=./data/events_sport_luka_doncic.jsonl

# get the articles of the events acquired with the above command
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/events_sport_luka_doncic.jsonl \
    --save_to_file=./data/events_sport_luka_doncic
```

### Events about blockchain

```bash
# get the events mentioning blockchain
collect events \
    --max_repeat_request=5 \
    --concepts="blockchain" \
    --languages=eng,slv \
    --date_start=2021-01-01 \
    --save_to_file=./data/events_tech_blockchain.jsonl

# get the articles of the events acquired with the above command
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/events_tech_blockchain.jsonl \
    --save_to_file=./data/events_tech_blockchain
```

### Events about journalism

```bash
# get the events mentioning journalism
collect events \
    --max_repeat_request=5 \
    --concepts="journalism,politics" \
    --languages=eng,slv \
    --date_start=2021-01-01 \
    --save_to_file=./data/events_politics_journalism.jsonl

# get the articles of the events acquired with the above command
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/events_politics_journalism.jsonl \
    --save_to_file=./data/events_politics_journalism
```

### Complex query: Slovenian EU presidency (excluding sports)

```bash
# 1. find the exact concept URIs to use
collect suggest concepts "slovenia" --types=loc
collect suggest concepts "council of the european union"

# 2. put the chosen URIs into a query file (see queries/eu_presidency.json)

# 3. collect the events matching the complex query
collect events \
    --max_repeat_request=5 \
    --query_file=./queries/eu_presidency.json \
    --save_to_file=./data/events_eu_presidency.jsonl

# 4. get the articles of the collected events
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/events_eu_presidency.jsonl \
    --save_to_file=./data/events_eu_presidency
```
