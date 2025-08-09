import os
import json
import requests
from typing import Dict, List


SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")


def post_assist_message(channel: str, payload: Dict) -> str:
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    resp = requests.post(url, headers=headers, json={"channel": channel, **payload})
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack error: {data}")
    return data.get("ts")


def reply_result(thread_ts: str, text: str):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    resp = requests.post(url, headers=headers, json={"channel": SLACK_CHANNEL_ID, "text": text, "thread_ts": thread_ts})
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack error: {data}")


