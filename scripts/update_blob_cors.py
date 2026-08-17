"""Patch Azure Blob CORS for local Cloudflare tunnel origins. Safe no-op without credentials."""
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env")
try:
    from azure.storage.blob import BlobServiceClient
    from azure.storage.blob._models import CorsRule
except ImportError:
    print("  azure-storage-blob not installed, skipping CORS update")
    sys.exit(0)

account_url = os.getenv("AZURE_BLOB_ACCOUNT_URL", "").rstrip("/")
account_key = os.getenv("AZURE_BLOB_ACCOUNT_KEY", "")
frontend_tunnel = os.getenv("FRONTEND_URL", "")
if not account_url or not account_key:
    print("  No Azure Blob credentials — skipping CORS update")
    sys.exit(0)

origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
]
if frontend_tunnel:
    origins.append(frontend_tunnel)

rule = CorsRule(
    allowed_origins=origins,
    allowed_methods=["GET", "PUT", "DELETE", "HEAD", "OPTIONS", "POST"],
    allowed_headers=["*"],
    exposed_headers=["*"],
    max_age_in_seconds=3600,
)
BlobServiceClient(account_url=account_url, credential=account_key).set_service_properties(cors=[rule])
print("  CORS updated for %s origins (incl. tunnel)" % len(origins))
