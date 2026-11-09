"""Schedule today's OCTO video on Buffer for TikTok and Instagram.

06:00 run (cron '0 23 * * *') -> post at 07:00 Asia/Ho_Chi_Minh.
18:00 run (cron '0 11 * * *') -> post at 19:00 Asia/Ho_Chi_Minh.
Manual runs (workflow_dispatch) default to the next 07:00 or 19:00 slot.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.buffer.com"
ICT = timezone(timedelta(hours=7))
TIKTOK_CHANNEL = "6ae71290e29c69a17125bdd6"   # mr.pump395
IG_CHANNEL = "6ae71222e29c69a17125ba7a"       # pumpmeme.crypto
REPO_RAW = "https://raw.githubusercontent.com/nguyentv2912/octo-videos/main/videos"


def slot_time(cron_expr: str) -> datetime:
    now = datetime.now(ICT)
    hour = 7 if cron_expr.strip() == "0 23 * * *" else 19 if cron_expr.strip() == "0 11 * * *" else (7 if now.hour < 12 else 19)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt } }
    ... on MutationError { message }
  }
}
"""


def main() -> int:
    token = os.environ["BUFFER_TOKEN"]
    name = os.environ["VIDEO_NAME"]
    stem = os.environ["STEM"]
    due = slot_time(os.environ.get("CRON_EXPR", ""))
    caption = open(f"videos/{stem}.txt", encoding="utf-8").read().strip()
    video_url = f"{REPO_RAW}/{name}"
    dueAt = due.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    print("video:", video_url, "due:", due.isoformat(), dueAt)

    jobs = [
        ("tiktok", TIKTOK_CHANNEL, {"tiktok": {"title": "Capital → profit: AI scans Solana meme coin signals (illustrative)", "isAiGenerated": True}}),
        ("instagram", IG_CHANNEL, {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}}),
    ]
    failed = False
    for label, channel, metadata in jobs:
        variables = {"input": {
            "text": caption,
            "channelId": channel,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": dueAt,
            "assets": [{"video": {"url": video_url}}],
            "metadata": metadata,
        }}
        try:
            out = graphql(token, CREATE_POST, variables)
            print(label, "->", json.dumps(out["createPost"], ensure_ascii=False))
        except Exception as exc:  # keep going so the other platform still gets scheduled
            failed = True
            print(label, "FAILED:", exc, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
