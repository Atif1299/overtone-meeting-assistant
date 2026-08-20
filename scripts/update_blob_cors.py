"""Patch GCS bucket CORS for dashboard, presenter, and localhost origins."""
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env")

bucket_name = os.getenv("GCS_BUCKET", "").strip()
if not bucket_name:
    print("  No GCS_BUCKET — skipping CORS update")
    sys.exit(0)

try:
    from google.cloud import storage
except ImportError:
    print("  google-cloud-storage not installed, skipping CORS update")
    sys.exit(0)

origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
]
for key in ("FRONTEND_URL", "BACKEND_URL", "DASHBOARD_URL"):
    value = os.getenv(key, "").strip()
    if value:
        origins.append(value.rstrip("/"))

cors = [
    {
        "origin": origins,
        "method": ["GET", "PUT", "HEAD", "OPTIONS", "POST", "DELETE"],
        "responseHeader": ["Content-Type", "Content-Length", "Content-Range"],
        "maxAgeSeconds": 3600,
    }
]
client = storage.Client()
bucket = client.bucket(bucket_name)
bucket.cors = cors
bucket.patch()
print("  GCS CORS updated for %s origins on gs://%s" % (len(origins), bucket_name))
