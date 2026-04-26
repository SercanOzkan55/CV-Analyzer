"""
Temporary download endpoints for local processing results.
Serves CSV/JSON exports with automatic cleanup.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import io

from utils.csv_exporter import get_temp_download as get_csv_download
from utils.json_exporter import get_temp_download as get_json_download

router = APIRouter(prefix="/api/v1/downloads", tags=["downloads"])


@router.get("/{download_id}")
async def download_file(download_id: str):
    """
    Download temporary file by ID.

    Files expire after 1 hour and are automatically cleaned up.
    """
    # Try CSV first
    download_data = get_csv_download(download_id)

    if not download_data:
        # Try JSON
        download_data = get_json_download(download_id)

    if not download_data:
        raise HTTPException(status_code=404, detail="Download not found or expired")

    # Create streaming response
    content_bytes = download_data['content'].encode('utf-8')

    def iter_content():
        yield content_bytes

    return StreamingResponse(
        iter_content(),
        media_type=download_data['content_type'],
        headers={
            "Content-Disposition": f'attachment; filename="{download_data["filename"]}"'
        }
    )


@router.get("/cleanup/expired")
async def cleanup_expired():
    """
    Clean up expired downloads (admin function).
    Returns number of cleaned up files.
    """
    from utils.csv_exporter import cleanup_expired_downloads as cleanup_csv
    from utils.json_exporter import cleanup_expired_downloads as cleanup_json

    csv_cleaned = cleanup_csv()
    json_cleaned = cleanup_json()

    return {
        "message": f"Cleaned up {csv_cleaned + json_cleaned} expired downloads",
        "csv_files": csv_cleaned,
        "json_files": json_cleaned
    }
