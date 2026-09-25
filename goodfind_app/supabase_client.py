"""
Supabase client and storage integration for GoodFind.

Provides a unified interface for connecting to Supabase PostgreSQL and Supabase Storage.
If SUPABASE_URL and SUPABASE_KEY are not configured, functions gracefully fall back.
"""
import os
import io
import uuid
import mimetypes
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "item-photos").strip()

_supabase_client = None


def is_supabase_enabled():
    """Return True only if valid Supabase URL and Key are provided."""
    return bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL.startswith("http"))


def get_supabase():
    """Get or create singleton Supabase client instance."""
    global _supabase_client
    if not is_supabase_enabled():
        return None
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"[Supabase] Failed to initialize client: {e}")
            return None
    return _supabase_client


def upload_to_storage(file_data, original_filename, org_id, kind="item"):
    """
    Upload image bytes or file stream to Supabase Storage.
    
    Returns:
        public_url (str) if successful, or None if Supabase is disabled / upload failed.
    """
    client = get_supabase()
    if not client:
        return None

    try:
        ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
        content_type = mimetypes.guess_type(original_filename)[0] or "image/jpeg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = f"{org_id}/{kind}/{unique_name}"

        if hasattr(file_data, "read"):
            data_bytes = file_data.read()
            if hasattr(file_data, "seek"):
                file_data.seek(0)
        elif isinstance(file_data, bytes):
            data_bytes = file_data
        else:
            return None

        # Upload to Supabase Storage bucket
        client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=data_bytes,
            file_options={"content-type": content_type, "cache-control": "3600", "upsert": "false"}
        )

        # Retrieve public URL
        public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
        return public_url
    except Exception as e:
        print(f"[Supabase Storage] Error uploading {original_filename}: {e}")
        return None
