import json
import os
from datetime import datetime

import gspread
from dotenv import load_dotenv

import instagram as ig

load_dotenv()
raw_json = os.getenv("GOOGLE_CREDS_JSON")
google_creds_dict = json.loads(raw_json)
gc = gspread.service_account_from_dict(google_creds_dict)
worksheet_key = os.getenv("WORKSHEET_ID")
sh = gc.open_by_key(worksheet_key)
worksheet_name = os.getenv("WORKSHEET_NAME")
worksheet = sh.worksheet(worksheet_name)

OFFSET = 5
ROW_MAX = 120

def get_post_recency(timestamp: datetime) -> str | None:
    difference = (datetime.today()-timestamp).days
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
    all_values = worksheet.get_all_values(value_render_option='FORMULA')[OFFSET-1:] 
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
    all_values, followers = get_all_gs_values()
    posts, follower = ig.get_all_media_data()
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
        'values': [[pretty_date(datetime.today())]]
    })    
    return result

def batch_update():
    if worksheet.acell(f'Z{OFFSET}').value == pretty_date(datetime.today()):
        return
    worksheet.batch_update(get_formatted_media_details(), value_input_option="USER_ENTERED")
    
def clear_all():
    if worksheet.acell(f'Z{OFFSET}').value == '': 
        return
    worksheet.batch_clear([f'A{OFFSET}:Z{ROW_MAX}'])    