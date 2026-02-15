"""
Admin endpoints for deployment operations.
Protected by ADMIN_API_KEY — used by GitHub Actions to push DB files to Railway.
"""
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Header, HTTPException

from app.db.schema import DB_DIR, UNIFIED_DB_PATH, REALPAGE_DB_PATH

router = APIRouter()

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")


def _check_admin_key(x_admin_key: str = Header(None)):
    if not ADMIN_API_KEY:
        raise HTTPException(503, "ADMIN_API_KEY not configured")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(403, "Invalid admin key")


@router.post("/admin/upload-db")
async def upload_db(
    db_type: str,
    file: UploadFile = File(...),
    x_admin_key: str = Header(None),
):
    """
    Upload a SQLite DB file to replace the current one.
    db_type: 'unified' | 'realpage' | 'yardi'
    """
    _check_admin_key(x_admin_key)

    db_map = {
        "unified": UNIFIED_DB_PATH,
        "realpage": REALPAGE_DB_PATH,
        "yardi": DB_DIR / "yardi_raw.db",
    }

    if db_type not in db_map:
        raise HTTPException(400, f"Invalid db_type: {db_type}. Use: {list(db_map.keys())}")

    target = db_map[db_type]
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then atomic rename
    tmp = target.with_suffix(".db.tmp")
    try:
        with open(tmp, "wb") as f:
            shutil.copyfileobj(file.file, f)
        # Atomic replace
        tmp.replace(target)
        size_mb = target.stat().st_size / (1024 * 1024)
        return {"status": "ok", "db_type": db_type, "size_mb": round(size_mb, 2), "path": str(target)}
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise HTTPException(500, f"Upload failed: {e}")


@router.post("/admin/upload-file")
async def upload_file(
    filename: str,
    file: UploadFile = File(...),
    x_admin_key: str = Header(None),
):
    """
    Upload a generic file to the data directory.
    Used for JSON cache files (reviews, etc.).
    """
    _check_admin_key(x_admin_key)

    # Only allow safe filenames
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-.")
    if not all(c in safe_chars for c in filename.lower()):
        raise HTTPException(400, f"Invalid filename: {filename}")

    target = DB_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(target, "wb") as f:
            shutil.copyfileobj(file.file, f)
        size_kb = target.stat().st_size / 1024
        return {"status": "ok", "filename": filename, "size_kb": round(size_kb, 1), "path": str(target)}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")


@router.get("/admin/db-status")
async def db_status(x_admin_key: str = Header(None)):
    """Check which DB files exist and their sizes."""
    _check_admin_key(x_admin_key)

    dbs = {
        "unified": UNIFIED_DB_PATH,
        "realpage": REALPAGE_DB_PATH,
        "yardi": DB_DIR / "yardi_raw.db",
    }

    result = {"db_dir": str(DB_DIR)}
    for name, path in dbs.items():
        if path.exists():
            stat = path.stat()
            result[name] = {
                "exists": True,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": stat.st_mtime,
            }
        else:
            result[name] = {"exists": False}

    return result
