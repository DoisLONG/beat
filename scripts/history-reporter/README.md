# MongoDB ChatHistory Query Tool

This script, `history-reporter.py`, is a tool for querying and aggregating EKBA service access history data from a MongoDB collection. It allows you to filter messages based on a minimum timestamp, group data by date, and export results in either CSV or console format.

## Usage

### Run on bare metal

#### Prerequisites

1. **Python 3.9 or higher** is required.
2. Install the required Python packages:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

#### Example 1: Print statistics for one week
```
python3 history-reporter.py --host localhost --database OPEA --collection ChatHistory
```

#### Example 2: Export statistics to CSV
```
python3 history-reporter.py --host localhost --database OPEA --collection ChatHistory --start-time "2025-03-12 08:00:01" --output-dir "output"
```

#### More options

Run the script using the following command:
```
EKBA history reporting tool

usage: history-reporter.py [-h] [-s HOST] [--port PORT] [-u USERNAME] [-p PASSWORD]
                           [--auth-source AUTH_SOURCE] -d DATABASE -c COLLECTION
                           [--start-time START_TIME] [--end-time END_TIME]
                           [--timezone TIMEZONE] [--output-dir OUTPUT_DIR]

options:
  -h, --help            show this help message and exit

Connection Configuration:
  -s HOST, --host HOST  MongoDB host address
  --port PORT           MongoDB port
  -u USERNAME, --username USERNAME
                        Authentication username
  -p PASSWORD, --password PASSWORD
                        Authentication password
  --auth-source AUTH_SOURCE
                        Authentication database
  -d DATABASE, --database DATABASE
                        Target database name
  -c COLLECTION, --collection COLLECTION
                        Target collection name

Query Parameters:
  --start-time START_TIME
                        Filter data starting from start_time (format: YYYY-MM-DD HH:MM:SS)
  --end-time END_TIME   Filter data ending at end_time (format: YYYY-MM-DD HH:MM:SS)
  --timezone TIMEZONE   Timezone setting (default: Asia/Shanghai)

Output Configuration:
  --output-dir OUTPUT_DIR
                        The dir to store the output files (in csv). If not specified,
                        will just print out.
```

### Run with docker compose

The script parameters are controlled by environment variables. before running, you need to copy the `env.example` to `.env` and modify `.env` according to your needs.

```bash
cp env.example .env
# modify .env based on your needs.
docker compose build
docker compose up
```

## Output

If you configure the `--output-dir`, the script can generate two CSV files:

- output_OPEA_ChatHistory_stats.csv: Contains statistics grouped by date. Including each request send by user, the columns are:
    - query (request content)
    - role (currently all are 'user')
    - timestamp
    - knowledge_base (currently all empty, need to improve)
    - trace_length (the docs traced by the request)
- output_OPEA_ChatHistory_token_usage.csv: Contains the token usage for each question and answer pair. The columns are:
    - timestamp
    - prompt_tokens
    - completion_tokens

1. Statistics grouped by date:
```
Statistics grouped by date:
      date  count
2025-03-12      5
```
2. Query results:
```
query                                          , role, timestamp          , knowledge_base, trace_length
你是谁                                         , user, 2025-03-25 16:51:53,               ,            1
百济神州有限公司2024年第三季度财报总结?          , user, 2025-03-25 16:53:21,               ,            1
今天天气好吗                                   , user, 2025-03-25 16:56:29,               ,            0
你是谁                                         , user, 2025-03-26 11:30:38,               ,            2
百济神州有限公司2024年第三季度财报总结???        , user, 2025-03-26 11:31:27,               ,            2
今天天气如何                                   , user, 2025-03-26 11:40:44,               ,            2
我问的是天气                                   , user, 2025-03-26 11:41:30,               ,            2
今天的天气是晴天还是阴天                        , user, 2025-03-26 11:42:02,               ,            2
介绍一下中国                                   , user, 2025-03-26 11:43:37,               ,            2

          timestamp  prompt_tokens  completion_tokens
2025-03-25 16:26:05              0                  0
2025-03-25 16:26:31              0                  0
2025-03-25 16:27:35              0                  0
2025-03-25 16:27:59              0                  0
2025-03-25 16:45:58              0                  0
2025-03-25 16:49:09              0                  0
2025-03-25 16:51:55             14                 42
2025-03-25 16:53:33            232                356
2025-03-25 16:56:30             12                 26
2025-03-26 11:30:41             14                 42
2025-03-26 11:31:43            231                526
2025-03-26 11:40:57            674                378
2025-03-26 11:41:43            530                398
```
