import json
import os
from datetime import datetime, timedelta, timezone
from pprint import pprint
from typing import Any, Iterable, Literal, MutableMapping, Optional, cast

import gspread
from dotenv import load_dotenv
from gspread.utils import ValueInputOption, ValueRenderOption

import instagram.instagram as ig
import sheets.types as t
from helpers.helpers import print_error, print_success

load_dotenv(override=True)

START_ROW = 5
ROW_MAX = 120


def get_worksheet() -> Optional[gspread.Worksheet]:
    try:
        raw_json: str = os.environ["GOOGLE_CREDS_JSON"]
        sheet_id: str = os.environ["WORKSHEET_ID"]
        sheet_name: str = os.environ["WORKSHEET_NAME"]

        credentials = json.loads(raw_json)
        client = gspread.service_account_from_dict(credentials)
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)

        print_success("Google Sheets connection initialized successfully")
        return sheet
    except KeyError as e:
        print_error("Missing required environment variables")
        print_error(e)
    except json.JSONDecodeError as e:
        print_error("GOOGLE_CREDS_JSON is not valid JSON")
        print_error(e)
    except gspread.exceptions.SpreadsheetNotFound as e:
        print_error("Spreadsheet not found or service account lacks permissions.")
        print_error(e)
    except gspread.exceptions.WorksheetNotFound as e:
        print_error("Worksheet name not found in the spreadsheet.")
        print_error(e)
    except Exception as e:
        print_error("Failed to initialize Google Sheets client.")
        print_error(e)
    return None


def calculate_recency(timestamp: datetime) -> Optional[t.Recency]:
    days_old = (datetime.now(timezone.utc) - timestamp).days
    if days_old < 7:
        return None
    if 7 <= days_old <= 13:
        return t.Recency.week1
    if 14 <= days_old <= 29:
        return t.Recency.week2
    return t.Recency.month


def format_date(date_obj: datetime) -> str:
    return f"{date_obj.year}/{date_obj.month}/{date_obj.day}"


def parse_google_date_serial(serial: Any) -> datetime:
    try:
        return datetime(1899, 12, 30) + timedelta(days=int(serial))
    except (ValueError, TypeError):
        return datetime(1970, 1, 1)


def build_range_string(
    index: int, range_key: t.Recency | Literal["metadata", "all_range"]
) -> str:
    columns = t.COLUMN_RANGES[range_key]
    return f"{columns.start}{index + START_ROW}:{columns.end}{index + START_ROW}"


def fetch_historical_data(
    sheet: gspread.Worksheet,
) -> Optional[tuple[t.HistoricalMetricsMap, t.FollowerCounts]]:
    def parse_metrics(values: list[Any]) -> list[int | str]:
        return [int(v) if str(v).strip() != "" else v for v in values]

    try:
        raw_rows = sheet.get_all_values(value_render_option=ValueRenderOption.formula)[
            START_ROW - 1 :
        ]
        follower_history: t.FollowerCounts = []
        metrics_map: t.HistoricalMetricsMap = {}

        for row in raw_rows:
            if row[0] != "":
                metrics_map[row[0]] = t.HistoricalMetrics(
                    date=parse_google_date_serial(row[1]),
                    title=row[2],
                    week1=parse_metrics(row[3:10]),
                    week2=parse_metrics(row[10:17]),
                    month=parse_metrics(row[17:24]),
                )
            if len(row) > 24 and str(row[24]).strip() != "":
                follower_history.append([int(row[24])])

        return metrics_map, follower_history
    except Exception as e:
        print_error(f"worksheet.get_all_values failed: {e}")
    return None


def _clear_cells_by_recency(index: int, recency: t.Recency) -> t.UpdatePayload:
    return {"range": build_range_string(index, recency), "values": [[""] * 7]}


def generate_update_payload(
    sheet: gspread.Worksheet,
) -> Optional[list[t.UpdatePayload]]:
    instagram_data = ig.fetch_media_data()
    if not instagram_data:
        return None
    current_posts, current_followers = instagram_data

    historical_data = fetch_historical_data(sheet)
    if not historical_data:
        return None
    past_metrics, follower_history = historical_data

    def identify_archived_posts(saved_posts: dict, active_posts: set) -> list[str]:
        return [
            post_id for post_id in saved_posts.keys() if post_id not in active_posts
        ]

    follower_history = [[current_followers]] + follower_history
    archived_post_ids = identify_archived_posts(
        past_metrics, {post.id for post in current_posts}
    )

    payload: list[t.UpdatePayload] = []
    row_index = 0

    for post in current_posts:
        recency = calculate_recency(post.timestamp)
        if not recency:
            continue

        post_id = post.id
        formatted_date = format_date(post.timestamp)
        url, caption = post.identifier
        title_formula = f'=HYPERLINK("{url}","{caption}")'

        metrics = post.metrics
        current_values: list[int | str] = [
            metrics["likes"],
            metrics["comments"],
            metrics["shares"],
            metrics.get("follows", ""),
            metrics["reach"],
            metrics["total_interactions"],
            metrics["views"],
        ]

        metadata_range = build_range_string(row_index, "metadata")
        metrics_range = build_range_string(row_index, recency)

        payload.append(
            {
                "range": metadata_range,
                "values": [[post_id, formatted_date, title_formula]],
            }
        )

        # Only 2 of these 3 conditions would succeed
        if recency != t.Recency.week1:
            payload.append(
                _clear_cells_by_recency(row_index, t.Recency.week1)
                if post_id not in past_metrics
                else {
                    "range": build_range_string(row_index, t.Recency.week1),
                    "values": [past_metrics[post_id].week1],
                }
            )
        if recency != t.Recency.week2:
            payload.append(
                _clear_cells_by_recency(row_index, t.Recency.week2)
                if post_id not in past_metrics
                else {
                    "range": build_range_string(row_index, t.Recency.week2),
                    "values": [past_metrics[post_id].week2],
                }
            )
        if recency != t.Recency.month:
            payload.append(
                _clear_cells_by_recency(row_index, t.Recency.month)
                if post_id not in past_metrics
                else {
                    "range": build_range_string(row_index, t.Recency.month),
                    "values": [past_metrics[post_id].month],
                }
            )

        # This is the above condition that did not succeed
        payload.append({"range": metrics_range, "values": [current_values]})
        row_index += 1

    for post_id in archived_post_ids:
        saved_date = format_date(past_metrics[post_id].date)
        saved_title = past_metrics[post_id].title
        payload.append(
            {
                "range": build_range_string(row_index, "all_range"),
                "values": [
                    [post_id, saved_date, saved_title]
                    + past_metrics[post_id].week1
                    + past_metrics[post_id].week2
                    + past_metrics[post_id].month
                ],
            }
        )
        row_index += 1

    payload.append(
        {
            "range": f"Y{START_ROW}:Y{START_ROW + len(follower_history) - 1}",
            "values": follower_history,
        }
    )

    run_timestamp = format_date(datetime.now(timezone.utc) - timedelta(hours=5))
    payload.append({"range": f"Z{START_ROW}", "values": [[run_timestamp]]})

    return payload


def run_etl_update() -> None:
    sheet = get_worksheet()
    if not sheet:
        print_error("Worksheet is not initialized; update aborted.")
        return None

    try:
        last_run_date = sheet.acell(f"Z{START_ROW}").value
    except gspread.exceptions.APIError as e:
        print_error(
            f"Google Sheets API error: Failed to read last run cell Z{START_ROW}: {e}"
        )
        last_run_date = None
    except Exception as e:
        print_error(f"Unexpected error reading last run cell: {e}")
        last_run_date = None

    today_est = format_date(datetime.now(timezone.utc) - timedelta(hours=5))

    if last_run_date == today_est:
        print_success("ETL already ran today; skipping update.")
        return None

    update_payload = generate_update_payload(sheet)

    if not update_payload:
        print_error("No update payload produced. Skipping update.")
        return None

    pprint(update_payload)

    try:
        response = sheet.batch_update(
            cast(Iterable[MutableMapping[str, Any]], update_payload),
            value_input_option=ValueInputOption.user_entered,
        )
        print("Batch Update Response:")
        pprint(response)
        print_success("Sheet update succeeded")
    except gspread.exceptions.APIError as e:
        print_error(f"Google Sheets API error during update: {e}")
    except Exception as e:
        print_error(f"Unexpected error in update: {e}")
    return None


def clear_worksheet() -> None:
    sheet = get_worksheet()
    if not sheet:
        print_error("Worksheet is not initialized; clear aborted.")
        return None

    try:
        last_run_date = sheet.acell(f"Z{START_ROW}").value
        if not last_run_date:
            print_success("Sheet appears empty, skipping clear.")
            return None

        target_range = f"A{START_ROW}:Z{ROW_MAX}"

        response = sheet.batch_clear([target_range])
        pprint(response)
        print_success(f"Sheet cleared range {target_range}.")
    except gspread.exceptions.APIError as e:
        print_error(f"Google Sheets API error during clear: {e}")
    except Exception as e:
        print_error(f"Unexpected error in clear: {e}")
    return None
