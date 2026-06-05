# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3

import os, sys
import argparse
from urllib.parse import quote_plus
from datetime import datetime, timedelta

from pytz import timezone
from pymongo import MongoClient
import pandas

def parse_arguments():
    parser = argparse.ArgumentParser(description='EKBA history reporting tool')
    
    # Connection parameters group
    conn_group = parser.add_argument_group('Connection Configuration')
    conn_group.add_argument('-s', '--host', default='localhost', help='MongoDB host address')
    conn_group.add_argument('--port', type=int, default=27017, help='MongoDB port')
    conn_group.add_argument('-u', '--username', help='Authentication username')
    conn_group.add_argument('-p', '--password', help='Authentication password')
    conn_group.add_argument('--auth-source', default='admin', help='Authentication database')
    conn_group.add_argument('-d', '--database', default='OPEA', required=True, help='Target database name')
    conn_group.add_argument('-c', '--collection', default='ChatHistory', required=True, help='Target collection name')

    # Query parameters group
    query_group = parser.add_argument_group('Query Parameters')
    query_group.add_argument('--start-time', default="",
                            help='Filter data starting from start_time (format: YYYY-MM-DD HH:MM:SS)')
    query_group.add_argument('--end-time', default="",
                            help='Filter data ending at end_time (format: YYYY-MM-DD HH:MM:SS)')
    query_group.add_argument('--timezone', default='Asia/Shanghai',
                            help='Timezone setting (default: Asia/Shanghai)')
    
    # Output parameters group
    output_group = parser.add_argument_group('Output Configuration')
    output_group.add_argument('--output-dir', default="", 
                            help='The dir to store the output files (in csv). If not specified, will just print out.')

    return parser.parse_args()

def build_connection(args):
    if args.username and args.password:
        uri = f"mongodb://{quote_plus(args.username)}:{quote_plus(args.password)}@"\
              f"{args.host}:{args.port}/{args.database}?authSource={args.auth_source}"
        return MongoClient(uri)
    else:
        return MongoClient(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            authSource=args.auth_source
        )

def convert_date_to_timestamp(date_str, tz_str):
    local_tz = timezone(tz_str)
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    local_dt = local_tz.localize(dt)  # Localize the datetime to the specified timezone
    utc_dt = local_dt.astimezone(timezone('UTC'))  # Convert to UTC
    return int(utc_dt.timestamp())

def convert_timestamp_to_date(timestamp, tz_str):
    try:
        dt = datetime.fromtimestamp(timestamp, timezone(tz_str))
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError) as e:
        formatted_time = "wrong time format"
        print(f"Exception converting timestamp to date:{timestamp} - {str(e)}")
    return formatted_time

def export_statistics_by_date(df):
    """export statistics grouped by date."""
    stats_df = df.copy()
    stats_df['date'] = pandas.to_datetime(stats_df['timestamp']).dt.date
    stats_df = stats_df.groupby('date').size().reset_index(name='count')
    return stats_df

def export_statistics(start_timestamp, end_timestamp, collection):
    pipeline = [
            {"$project": {
                "filteredMessages": {
                    "$filter": {
                        "input": "$data.messages",
                        "as": "msg",
                        "cond": {
                            "$and": [
                                {"$eq": ["$$msg.role", "user"]},
                                {"$gte": [{"$toInt": "$$msg.time"}, start_timestamp]},
                                {"$lte": [{"$toInt": "$$msg.time"}, end_timestamp]}
                            ]
                        }
                    }
                },
                "collection_name": "$data.collection_name",
                "last_query_trace_data_length": {
                    "$size": "$data.last_query_trace_data"
                    }
                }
            },
            {
                "$match": {
                    "filteredMessages.0": {"$exists": True}
                }
            },
            {
                "$unwind": "$filteredMessages"
            },
            {
                "$sort": {
                    "filteredMessages.time": 1
                }
            },
            {"$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": [
                        "$filteredMessages",
                        {
                            "collection_name": "$collection_name",
                            "last_query_trace_data_length": "$last_query_trace_data_length"
                        }
                    ]
                }
            }
        }
    ]
    results = collection.aggregate(pipeline)
    df = pandas.DataFrame([{
        'query': r.get('content'),
        'role': r.get('role'),
        'timestamp': convert_timestamp_to_date(int(r.get('time')), args.timezone),
        'knowledge_base': r.get('collection_name'),
        'trace_length': r.get('last_query_trace_data_length')
    } for r in results])
    return df

def export_token_usage(start_timestamp, end_timestamp, collection):
    pipeline = [
        {"$unwind": "$data.messages"},
        {"$match": {
            "data.messages.role": "assistant",
            "data.messages.token_usage": {"$exists": True},
            "$expr": {
                "$and": [
                    {"$gte": [{"$toInt": "$data.messages.time"}, start_timestamp]},
                    {"$lte": [{"$toInt": "$data.messages.time"}, end_timestamp]}
                ]
            }
        }},
        {"$project": {
            "timestamp": {"$toInt": "$data.messages.time"},
            "prompt_tokens": "$data.messages.token_usage.prompt_tokens",
            "completion_tokens": "$data.messages.token_usage.completion_tokens"
        }}
    ]
    results = collection.aggregate(pipeline)
    df = pandas.DataFrame([{
        'timestamp': convert_timestamp_to_date(r.get('timestamp'), args.timezone),
        'prompt_tokens': r.get('prompt_tokens', 0),
        'completion_tokens': r.get('completion_tokens', 0)
    } for r in results])
    return df

def export_format(datatype: str, df, output_file=None):
    """Export statistics based on the output format."""
    print(f"Export {datatype} from {args.start_time} to {args.end_time}")
    if not output_file:
        print(df.to_string(index=False))
    else:
        print(f"\tin: {output_file}")
        df.to_csv(output_file, index=False)
    print()

args = parse_arguments()

def main():
    try:
        client = build_connection(args)
        db = client[args.database]
        collection = db[args.collection]
        if not args.start_time:
            args.start_time = (datetime.now(timezone(args.timezone))-timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        start_timestamp = convert_date_to_timestamp(args.start_time, args.timezone)
        if not args.end_time:
            args.end_time = datetime.now(timezone(args.timezone)).strftime('%Y-%m-%d %H:%M:%S')
        end_timestamp = convert_date_to_timestamp(args.end_time, args.timezone)

        access_details = export_statistics(start_timestamp,end_timestamp, collection)
        if access_details.empty:
            print(f"\033[91mNo data found from {args.start_time} to {args.end_time}\033[0m")
            return 1
        
        access_sum = export_statistics_by_date(access_details)
        token_usage = export_token_usage(start_timestamp, end_timestamp, collection)

        if args.output_dir:
            if not os.path.exists(args.output_dir):
                os.makedirs(args.output_dir)

            access_sum_file = os.path.join(args.output_dir, f"{args.database}_{args.collection}_access_sum.csv")
            access_details_file = os.path.join(args.output_dir, f"{args.database}_{args.collection}_access_details.csv")
            token_usage_file = os.path.join(args.output_dir, f"{args.database}_{args.collection}_token_usage.csv")

            export_format("access sum", access_sum, access_sum_file)
            export_format("access details", access_details, access_details_file)
            export_format("token usage", token_usage, token_usage_file)
        else:
            export_format("access sum", access_sum)
            export_format("access details", access_details)
            export_format("token usage", token_usage)

    except ValueError as ve:
        print(f"\033[91mError occurred: {str(ve)}\033[0m")
    except Exception as e:
        print(f"\033[91mUnknown error occurred: {str(e)}\033[0m")

    return 0
if __name__ == "__main__":
    sys.exit(main())
