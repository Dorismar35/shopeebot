import requests
import json
import time
import os
from pathlib import Path

# Config
AUTH = "ZG9yaXNtYXIyMUBnbWFpbC5jb20:2HYiDmMpWmPVV1nEMcjL9"
IMG_PATH = r"C:\Users\Dorismar\.gemini\antigravity\brain\92f9bf43-f172-46e8-99bb-f3ee3c5c53bd\avatar_masculino_shopee_1776465606145.png"
AUD_PATH = r"C:\Users\Dorismar\Desktop\ShopeeBot\banco\audios\Fone_Bluetooth_TWS_P.mp3"

def upload_file(path):
    print(f"Uploading {path}...")
    with open(path, 'rb') as f:
        resp = requests.post('https://uguu.se/upload.php', files={'files[]': f})
        return resp.json()['files'][0]['url']

try:
    img_url = upload_file(IMG_PATH)
    aud_url = upload_file(AUD_PATH)
    print(f"Image URL: {img_url}")
    print(f"Audio URL: {aud_url}")

    payload = {
        "script": {
            "type": "audio",
            "audio_url": aud_url
        },
        "source_url": img_url,
        "config": {
            "fluent": True,
            "pad_audio": 0.0
        }
    }

    print("Creating talk...")
    resp = requests.post(
        'https://api.d-id.com/talks',
        headers={
            'Authorization': f'Basic {AUTH}',
            'Content-Type': 'application/json'
        },
        json=payload
    )
    
    if resp.status_code != 201:
        print(f"Error creating talk: {resp.status_code}")
        print(resp.text)
        exit()

    talk_id = resp.json()['id']
    print(f"Talk ID: {talk_id}")

    # Polling
    while True:
        print("Checking status...")
        resp = requests.get(
            f'https://api.d-id.com/talks/{talk_id}',
            headers={'Authorization': f'Basic {AUTH}'}
        )
        data = resp.json()
        status = data.get('status')
        print(f"Status: {status}")
        
        if status == 'done':
            video_url = data.get('result_url')
            print(f"Video ready! URL: {video_url}")
            # Download video
            vid_resp = requests.get(video_url)
            out_path = Path(AUD_PATH).parent.parent / "videos" / "avatar_teste_did.mp4"
            with open(out_path, 'wb') as f:
                f.write(vid_resp.content)
            print(f"Video saved to: {out_path}")
            break
        elif status == 'error':
            print("Error generating video")
            print(data)
            break
        
        time.sleep(5)

except Exception as e:
    print(f"Exception: {e}")
