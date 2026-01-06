import json
import os
from datetime import datetime, timedelta

import demoji
import requests
from dotenv import load_dotenv

load_dotenv()
try:
    token = os.getenv("ACCESS_TOKEN")
    if not token:
        raise Exception("MISSING Access Token")
    user_id = os.getenv("USER_ID")
    if not user_id:
        raise Exception("MISSING user id")
except Exception as e:
    print(f"error: Failed to initialize Google Sheets client: {e}")

DATE_OFFSET = 40

def utc_to_est(iso_date: str) -> datetime:
    local_convertion: datetime = datetime.fromisoformat(iso_date).astimezone(None)
    return datetime(local_convertion.year, local_convertion.month, local_convertion.day)

def est_to_utc(dt: datetime):
    return dt + timedelta(hours=5)

def forty_day_limit():
    return int((est_to_utc(datetime.today()) - timedelta(days=DATE_OFFSET)).timestamp())

def shorten_caption(caption: str):
    
    return ' '.join(demoji.replace(caption, repl="").split(" ")[:5]).replace("\n", "").replace(",", "")

def get_all_media_data() -> (dict | int):
    if not user_id or not token: 
        return None
    media_url = f'https://graph.instagram.com/v24.0/{user_id}?fields=followers_count,media.since({forty_day_limit()}).fields(id,permalink,timestamp,caption,insights.metric(comments,follows,likes,reach,shares,total_interactions,views))&access_token={token}'
    
    try:
        media_url_response = requests.get(media_url)
        media_url_obj = json.loads(media_url_response.text)
        
        result = []
        
        for media in media_url_obj["media"]["data"]:
            result.append({
                "id": media["id"],
                "metrics": {insight["name"]: insight["values"][0]["value"] for insight in media["insights"]["data"]},
                "timestamp": utc_to_est(media["timestamp"]),
                "identifier":(media["permalink"], shorten_caption(media["caption"] if "caption" in media else ""))
            })
        return (result, media_url_obj["followers_count"])
    except requests.HTTPError as e:
        print(f"Instagram API HTTP error: {e}")
        return None
    except requests.RequestException as re:
        print(f"Instagram API request failed: {re}")
        return None 
    except requests.Timeout as te:
        print(f"Instagram API request timed out {te}")
        return None
    except ValueError:
        print("Instagram API returned invalid JSON")
        return None    
    except Exception as e:
        print(e)
        return None