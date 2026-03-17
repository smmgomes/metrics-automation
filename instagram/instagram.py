import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

import demoji
import requests
from dotenv import load_dotenv

import instagram.types as t
from helpers.helpers import print_error, print_success

load_dotenv(override=True)

DAYS_SINCE_OFFSET = 40


def build_api_url() -> Optional[str]:
    try:
        access_token = os.environ["ACCESS_TOKEN"]
        user_id = os.environ["USER_ID"]

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_SINCE_OFFSET)
        cutoff_timestamp = int(cutoff_date.timestamp())

        insight_metrics = "comments,follows,likes,reach,shares,total_interactions,views"
        media_fields = (
            f"id,permalink,timestamp,caption,insights.metric({insight_metrics})"
        )
        user_fields = (
            f"followers_count,media.since({cutoff_timestamp}).fields({media_fields})"
        )

        base_url = f"https://graph.instagram.com/v24.0/{user_id}"

        print_success("Retrieved Instagram TOKEN and USER ID; built URL successfully.")
        return f"{base_url}?fields={user_fields}&access_token={access_token}"
    except KeyError as e:
        print_error(f"Missing required environment variable: {e}")
    except Exception as e:
        print_error(f"Unexpected error building Instagram fetch URL: {e}")

    return None


def _format_caption(caption: str) -> str:
    return (
        " ".join(demoji.replace(caption, repl="").split(" ")[:5])
        .replace("\n", "")
        .replace(",", "")
    )


def _parse_timestamp(iso_date: str) -> datetime:
    time = datetime.fromisoformat(iso_date)
    return datetime(time.year, time.month, time.day).astimezone(tz=timezone.utc)


def fetch_media_data() -> Optional[t.ExtractedMediaPayload]:
    api_url = build_api_url()
    if not api_url:
        return None

    try:
        response = requests.get(api_url)

        if not response.ok:
            raise Exception(response.text)

        payload: t.APIUserMediaResponse = json.loads(response.text)
        print_success("Instagram API Response received and json parsed")

        processed_posts = [
            t.ProcessedPost(
                id=media["id"],
                metrics=cast(
                    t.PostMetrics,
                    {
                        metric["name"]: metric["values"][0]["value"]
                        for metric in media["insights"]["data"]
                    },
                ),
                timestamp=_parse_timestamp(media["timestamp"]),
                identifier=(
                    media["permalink"],
                    _format_caption(media.get("caption", "")),
                ),
            )
            for media in payload["media"]["data"]
        ]

        print_success("Instagram Insights Per Media Extracted")
        return processed_posts, payload["followers_count"]

    except requests.HTTPError as e:
        print_error(f"Instagram API HTTP error: {e}")
        return None
    except requests.RequestException as e:
        print_error(f"Instagram API request failed: {e}")
        return None
    except ValueError:
        print_error("Instagram API returned invalid JSON")
        return None
    except Exception as e:
        print_error(str(e))
        return None
