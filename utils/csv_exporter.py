"""
CSV export utilities for local processing results.
Generates downloadable CSV files with temporary URLs.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

# In-memory storage for temporary downloads (in production, use Redis/S3)
_temp_downloads = {}


def generate_csv_download(results: List[Dict[str, Any]], job_id: int) -> str:
    """
    Generate CSV content and return download URL.

    Args:
        results: Processing results
        job_id: Job ID for filename

    Returns:
        Download URL (temporary, expires in 1 hour)
    """
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Filename', 'Status', 'Final Score', 'ATS Score',
        'Skills Match', 'Experience Match', 'Education Match',
        'Processed At', 'Job ID'
    ])

    # Write data
    for result in results:
        writer.writerow([
            result.get('filename', ''),
            result.get('status', ''),
            result.get('final_score', 0),
            result.get('ats_score', 0),
            '; '.join(result.get('skills_match', [])),
            result.get('experience_match', 0),
            result.get('education_match', 0),
            result.get('processed_at', ''),
            result.get('job_id', job_id)
        ])

    csv_content = output.getvalue()
    output.close()

    # Generate temporary download ID
    download_id = f"csv_{uuid.uuid4()}"
    expires_at = datetime.utcnow() + timedelta(hours=1)

    _temp_downloads[download_id] = {
        'content': csv_content,
        'content_type': 'text/csv',
        'filename': f'cv_rankings_job_{job_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        'expires_at': expires_at
    }

    return f"/api/v1/downloads/{download_id}"


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
    if datetime.utcnow() > download['expires_at']:
        del _temp_downloads[download_id]
        return None

    return download


def cleanup_expired_downloads():
    """Clean up expired temporary downloads."""
    current_time = datetime.utcnow()
    expired = [
        download_id for download_id, data in _temp_downloads.items()
        if current_time > data['expires_at']
    ]

    for download_id in expired:
        del _temp_downloads[download_id]

    return len(expired)
