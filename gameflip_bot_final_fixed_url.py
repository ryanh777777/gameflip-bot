
import requests
import json
import time
import csv
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta

# Load config
with open("config.json") as f:
    config = json.load(f)

API_KEY = config["GFAPI_KEY"]
API_SECRET = config["GFAPI_SECRET"]
USER_ID = "us-east-1:bd8308bc-12cc-4184-82d7-3c5588e7e5b1"
POST_INTERVAL = 120  # 2 minutes
EXPIRY_TIME = timedelta(hours=36)

BASE_URL = "https://api.gameflip.com"

# Load posted listings
try:
    with open("posted.json", "r") as f:
        posted_listings = json.load(f)
except FileNotFoundError:
    posted_listings = {}

def sign_request(path, method, body=""):
    nonce = str(uuid.uuid4())
    message = f"{path}{method}{nonce}{body}".encode("utf-8")
    signature = hmac.new(API_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "GF-API-KEY": API_KEY,
        "GF-API-NONCE": nonce,
        "GF-API-SIGNATURE": signature
    }
    return headers

def post_listing(data):
    path = "/listing"
    url = BASE_URL + path
    body = json.dumps(data)
    headers = sign_request(path, "POST", body)

    response = requests.post(url, headers=headers, data=body)
    if response.status_code == 200:
        result = response.json()
        listing_id = result.get("id")
        print(f"[+] Posted listing: {listing_id}")
        posted_listings[listing_id] = datetime.utcnow().isoformat()
        return listing_id
    else:
        print(f"[!] Failed to post: {response.status_code} - {response.text}")
        return None

def delete_listing(listing_id):
    path = f"/listing/{listing_id}"
    url = BASE_URL + path
    headers = sign_request(path, "DELETE")

    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        print(f"[-] Deleted listing: {listing_id}")
        posted_listings.pop(listing_id, None)
    else:
        print(f"[!] Failed to delete {listing_id}: {response.status_code} - {response.text}")

def build_listing(row):
    quantity = int(row.get("quantity", 1))
    title = row["title"]
    if config["post"].get("appendQuantity") and quantity > 1:
        title = f"{title} x{quantity}"

    return {
        "seller": {"id": USER_ID},
        "title": title,
        "description": row["description"],
        "price": int(float(row["price"]) * 100),  # Gameflip uses cents
        "currency": row.get("currency", "USD"),
        "expire_in": config["post"]["expiry"],
        "category": "Other",  # Force safe category
        "tags": row.get("tags", "").split(",") if row.get("tags") else [],
        "shipping": {"delivery_method": "transfer", "days_to_deliver": config["post"]["deliveryTime"]},
        "images": [row["image_url"]],
        "digital": True
    }

def purge_old_listings():
    now = datetime.utcnow()
    to_delete = [lid for lid, post_time in posted_listings.items()
                 if now - datetime.fromisoformat(post_time) > EXPIRY_TIME]

    for lid in to_delete:
        delete_listing(lid)

def main():
    with open("listings.csv", newline="", encoding="utf-8") as csvfile:
        reader = list(csv.DictReader(csvfile))
        index = 0

        while True:
            if index >= len(reader):
                index = 0  # loop forever

            purge_old_listings()

            row = reader[index]
            listing_data = build_listing(row)
            post_listing(listing_data)

            with open("posted.json", "w") as f:
                json.dump(posted_listings, f, indent=2)

            index += 1
            time.sleep(POST_INTERVAL)

if __name__ == "__main__":
    main()
