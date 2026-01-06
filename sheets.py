import json
import os
from datetime import datetime, timedelta

import gspread
from dotenv import load_dotenv

import instagram as ig

load_dotenv()

try:
    raw_json = os.getenv("GOOGLE_CREDS_JSON")
    if not raw_json:
        raise Exception("Missing GOOGLE_CREDS_JSON env var")

    try:
        google_creds_dict = json.loads(raw_json)
    except Exception:
        raise Exception("GOOGLE_CREDS_JSON is not valid JSON")

    worksheet_key = os.getenv("WORKSHEET_ID")
    if not worksheet_key:
        raise Exception("Missing WORKSHEET_ID env var")

    worksheet_name = os.getenv("WORKSHEET_NAME")
    if not worksheet_name:
        raise Exception("Missing WORKSHEET_NAME env var")

    gc = gspread.service_account_from_dict(google_creds_dict)
    sh = gc.open_by_key(worksheet_key)
    worksheet = sh.worksheet(worksheet_name)

    print("INFO: Google Sheets connection initialized successfully")

except Exception as e:
    print(f"error: Failed to initialize Google Sheets client: {e}")
    worksheet = None

OFFSET = 5
ROW_MAX = 120

def get_post_recency(timestamp: datetime) -> str | None:
    difference = ((datetime.today() - timedelta(hours=5))-timestamp).days
    if 7 <= difference <= 13:
         return 'week1'
    elif 14 <= difference <= 24:
        return 'week2'
    elif 30 <= difference <= 40:
        return 'month'
    else:
        return None 
  
def pretty_date(date: datetime) -> str:
    return str(date.year) + "/" + str(date.month) + "/" + str(date.day) 

def get_post_column_bucket(index: int, recency: str) -> str | None:
    if recency == 'week1':
        return 'D' + str(index+OFFSET) + ':' + 'J' + str(index+OFFSET) 
    elif recency == 'week2':
        return 'K' + str(index+OFFSET) + ':' + 'Q' + str(index+OFFSET)
    elif recency == 'month':
        return 'R' + str(index+OFFSET) + ':' + 'X' + str(index+OFFSET)
    else:
        return None   
    
def get_all_gs_values() -> (dict | list):
    try: 
        all_values = worksheet.get_all_values(value_render_option='FORMULA')[OFFSET-1:] 
    except Exception as e:
        print(f"error: worksheet.get_all_values failed: {e}")
        return ({}, [])
    followers = []
    result = {}
    for rows in all_values:
        if rows[0]!='':
            result[rows[0]] = {   
                    "date": rows[1],
                    "title": rows[2], 
                }
            if any(v != '' for v in rows[3:10]):
                result[rows[0]]["week1"] = [int(v) if v!='' else v for v in rows[3:10]]
            if  any(v != '' for v in rows[10:17]):
                result[rows[0]]["week2"] = [int(v) if v!='' else v for v in rows[10:17]]
            if  any(v != '' for v in rows[17:24]):
                result[rows[0]]["month"] = [int(v) if v!='' else v for v in rows[17:24]]
        if rows[24]!='':
            followers.append(rows[24])        
    return (result, list(map(int, followers)))

def check_if_existing_id(id: str, all_values: dict) -> bool:
    return id in all_values

def get_archived_ids(gs_rows: dict, ig_rows: set) -> list:
    return [mid for mid in gs_rows.keys() if mid not in ig_rows]

def get_formatted_media_details() -> list[dict]:
    ig_response = ig.get_all_media_data()
    if ig_response is None:
        return
    posts, follower = ig_response
    all_values, followers = get_all_gs_values()
    followers=[follower]+followers
    archived_ids = get_archived_ids(all_values, {ids["id"] for ids in posts})
    result = []
    index = 0
    for media in posts:
        recency = get_post_recency(media["timestamp"])
        if recency is None:
            continue
        m_id = media["id"]
        date = pretty_date(media["timestamp"])
        url, caption = media["identifier"]
        title = f'=HYPERLINK("{url}","{caption}")'
        likes = media["metrics"]["likes"]
        comments = media["metrics"]["comments"]
        shares = media["metrics"]["shares"]
        follows = media["metrics"]["follows"] if "follows" in media["metrics"] else ""
        reach = media["metrics"]["reach"]
        interactions = media["metrics"]["total_interactions"]
        views = media["metrics"]["views"]
        metadata_range = 'A' + str(index+OFFSET) + ':' + 'C' + str(index+OFFSET)
        ig_column_range = get_post_column_bucket(index, recency)
        
        result.append({
            'range': metadata_range,
            'values': [[m_id, date, title]]
        })
        
        if check_if_existing_id(m_id, all_values):
            for key, values in all_values[m_id].items():
                gs_column_range = get_post_column_bucket(index, key)
                if key!="date" and key!="title" and gs_column_range != ig_column_range:
                    result.append({
                        'range': get_post_column_bucket(index, key),
                        'values': [values]
                    }) 
        result.append({
            'range': get_post_column_bucket(index, recency),
            'values': [[likes, comments, shares, follows, reach, interactions, views]]
        })
        index+=1
        
    for mid in archived_ids:
        metadata_range = 'A' + str(index+OFFSET) + ':' + 'C' + str(index+OFFSET)
        result.append({
            'range': metadata_range,
            'values': [[mid, all_values[mid]["date"], all_values[mid]["title"]]]
        })
        if "week1" in all_values[mid]:
            result.append({
                'range': get_post_column_bucket(index, "week1"),
                'values': [all_values[mid]["week1"]]
            })
        if "week2" in all_values[mid]:
            result.append({
                'range': get_post_column_bucket(index, "week2"),
                'values': [all_values[mid]["week2"]]
            })
        if "month" in all_values[mid]:
            result.append({
                'range': get_post_column_bucket(index, "month"),
                'values': [all_values[mid]["month"]]
            })
        index+=1  

    for i, follow_count in enumerate(followers):
        result.append({
            'range': 'Y' + str(i+OFFSET),
            'values': [[follow_count]]
        })
    result.append({
        'range': 'Z' + str(OFFSET),
        'values': [[pretty_date(datetime.today() - timedelta(hours=5))]]
    })    
    return result

def batch_update():
    if worksheet is None:
        print("error: Worksheet is not initialized; batch_update aborted")
        return
    
    try:
        last_run = worksheet.acell(f"Z{OFFSET}").value
    except Exception as e:
        print(f"error: Failed to read last run cell Z{OFFSET}: {e}")
        last_run = None

    if last_run == pretty_date(datetime.today() - timedelta(hours=5)):
        print("ETL already ran today; skipping batch_update")
        return
    
    update_response = get_formatted_media_details()
    if update_response is None:
        print("No update payload produced; skipping batch_update")
        return
    try:
        worksheet.batch_update(update_response, value_input_option="USER_ENTERED")
        print(f"info: Sheet batch_update succeeded with {len(update_response)} updates")
    except Exception as e:
        print(f"error: worksheet.batch_update failed: {e}")
    
def clear_all():
    if worksheet is None:
        print("error: Worksheet is not initialized; clear_all aborted")
        return
    
    try:
        last_run = worksheet.acell(f"Z{OFFSET}").value
    except Exception as e:
        print(f"Failed to read last run cell Z{OFFSET}: {e}")
        last_run = None

    if last_run == "":
        print("Sheet appears empty, skipping clear_all")
        return
    try:
        worksheet.batch_clear([f"A{OFFSET}:Z{ROW_MAX}"])
        print(f"Sheet cleared range A{OFFSET}:Z{ROW_MAX}")
    except Exception as e:
        print(f"worksheet.batch_clear failed: {e}")    