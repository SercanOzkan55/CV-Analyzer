"""
JSON export utilities for local processing results.
Generates downloadable JSON files with temporary URLs.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from utils.download_security import sign_download_id

# In-memory storage for temporary downloads (in production, use Redis/S3)
_temp_downloads = {}


def generate_json_download(
    results: List[Dict[str, Any]],
    job_id: int,
    owner_organization_id: int | None = None,
    owner_subscription_id: int | None = None,
) -> str:
    """
    Generate JSON content and return download URL.

    Args:
        results: Processing results
        job_id: Job ID for filename

    Returns:
        Download URL (temporary, expires in 1 hour)
    """
    # Create JSON content
    json_data = {
        "metadata": {
            "job_id": job_id,
            "total_results": len(results),
            "exported_at": datetime.utcnow().isoformat(),
            "format_version": "1.0",
        },
        "results": results,
    }

    json_content = json.dumps(json_data, indent=2, ensure_ascii=False)

    # Generate temporary download ID
    download_id = f"json_{uuid.uuid4()}"
    expires_at = datetime.utcnow() + timedelta(hours=1)

    _temp_downloads[download_id] = {
        "content": json_content,
        "content_type": "application/json",
        "filename": f"cv_rankings_job_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        "expires_at": expires_at,
        "owner_organization_id": owner_organization_id,
        "owner_subscription_id": owner_subscription_id,
    }

    return f"/api/v1/downloads/{download_id}?token={sign_download_id(download_id)}"


def get_temp_download(download_id: str) -> Dict[str, Any]:
    """
    Get temporary download by ID.

    Args:
        download_id: Download ID

    Returns:
        Download data or None if expired/not found
    """
    if download_id not in _temp_downloads:
        return None

    download = _temp_downloads[download_id]

    # Check expiration
    if datetime.utcnow() > download["expires_at"]:
        del _temp_downloads[download_id]
        return None

    return download


def cleanup_expired_downloads():
    """Clean up expired temporary downloads."""
    current_time = datetime.utcnow()
    expired = [download_id for download_id, data in _temp_downloads.items() if current_time > data["expires_at"]]

    for download_id in expired:
        del _temp_downloads[download_id]

    return len(expired)
