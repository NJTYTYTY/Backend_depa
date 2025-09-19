"""
Media Asset Management API Endpoints
"""

import os
import shutil
import mimetypes
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
import logging

from ...storage import MediaAssetStorage, UserStorage, PondStorage
from ...schemas.media import (
    MediaAssetCreate, MediaAssetUpdate, MediaAssetResponse, MediaAssetList,
    MediaAssetFilter, MediaAssetUpload, MediaAssetStats, MediaAssetBulk,
    MediaAssetBulkResponse, MediaAssetSearch, MediaAssetSearchResponse
)
from ...api.dependencies import get_current_active_user, get_admin_user
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

# Configuration
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
    'video': {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'},
    'document': {'.pdf', '.doc', '.docx', '.txt', '.rtf'},
    'audio': {'.mp3', '.wav', '.ogg', '.aac', '.flac'}
}

def get_file_type(extension: str) -> str:
    """Determine file type based on extension"""
    extension = extension.lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return file_type
    return 'document'  # Default fallback

def get_mime_type(extension: str) -> str:
    """Get MIME type based on file extension"""
    mime_type, _ = mimetypes.guess_type(f"file{extension}")
    return mime_type or 'application/octet-stream'

def verify_pond_ownership(pond_id: int, current_user: dict) -> dict:
    """
    Verify pond ownership and return pond object
    """
    pond = PondStorage.get_by_id(pond_id)
    if not pond:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Pond not found"
        )
    
    # Admin can access all ponds, owners can access their own ponds
    if not current_user.get("is_admin", False) and pond.get("owner_id") != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this pond"
        )
    
    return pond

def validate_file_upload(file: UploadFile) -> tuple[str, str, str]:
    """Validate uploaded file and return file type, extension, and mime type"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    extension = Path(file.filename).suffix.lower()
    if not extension:
        raise HTTPException(status_code=400, detail="No file extension found")
    
    # Check if extension is allowed
    allowed_extensions = set()
    for ext_set in ALLOWED_EXTENSIONS.values():
        allowed_extensions.update(ext_set)
    
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File extension {extension} not allowed. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_type = get_file_type(extension)
    mime_type = get_mime_type(extension)
    
    return file_type, extension, mime_type

def save_uploaded_file(file: UploadFile, pond_id: int, filename: str) -> str:
    """Save uploaded file to disk and return file path"""
    # Create upload directory structure
    pond_upload_dir = UPLOAD_DIR / str(pond_id)
    pond_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_path = pond_upload_dir / filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return str(file_path)
    except Exception as e:
        logger.error(f"Failed to save file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

def delete_file_from_disk(file_path: str):
    """Delete file from disk"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")

@router.post("/upload", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_asset(
    pond_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
):
    """Upload a new media asset"""
    
    # Verify pond ownership or admin access
    verify_pond_ownership(pond_id, current_user)
    
    # Validate file
    file_type, extension, mime_type = validate_file_upload(file)
    
    # Check file size
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file.size} bytes exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
        )
    
    # Parse tags
    tag_list = []
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Generate unique filename
    timestamp = int(datetime.utcnow().timestamp())
    safe_filename = f"{timestamp}_{file.filename}"
    
    # Save file to disk
    file_path = save_uploaded_file(file, pond_id, safe_filename)
    
    # Create media asset record
    media_asset_data = {
        "title": title,
        "description": description,
        "file_type": file_type,
        "file_extension": extension,
        "file_size": file.size or 0,
        "mime_type": mime_type,
        "tags": tag_list,
        "is_public": is_public,
        "category": category,
        "pond_id": pond_id,
        "file_path": file_path,
        "original_filename": file.filename,
        "uploaded_by": current_user.get("id")
    }
    
    db_media_asset = MediaAssetStorage.create(media_asset_data)
    
    logger.info(f"Uploaded media asset: {title} for pond {pond_id} by user {current_user.get('id')}")
    
    return db_media_asset

@router.get("/assets", response_model=MediaAssetList)
async def list_media_assets(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    pond_id: Optional[int] = Query(None, description="Filter by pond ID"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    uploaded_by: Optional[int] = Query(None, description="Filter by uploader user ID"),
    is_public: Optional[bool] = Query(None, description="Filter by public/private status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    current_user: dict = Depends(get_current_active_user),
):
    """List media assets with filtering and pagination"""
    
    # Get all assets
    all_assets = MediaAssetStorage.get_all()
    
    # Apply filters
    filtered_assets = []
    
    for asset in all_assets:
        # Check pond access
        if pond_id:
            if asset.get('pond_id') != pond_id:
                continue
            # Verify pond ownership
            verify_pond_ownership(pond_id, current_user)
        
        # Apply other filters
        if file_type and asset.get('file_type') != file_type:
            continue
        if uploaded_by and asset.get('uploaded_by') != uploaded_by:
            continue
        if is_public is not None and asset.get('is_public') != is_public:
            continue
        if category and asset.get('category') != category:
            continue
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            asset_tags = asset.get('tags', [])
            if not any(tag in asset_tags for tag in tag_list):
                continue
        
        # Filter by visibility (user can see their own assets and public assets)
        if not current_user.get("is_admin", False):
            if asset.get('uploaded_by') != current_user.get('id') and not asset.get('is_public', False):
                continue
        
        filtered_assets.append(asset)
    
    # Get total count
    total = len(filtered_assets)
    
    # Apply pagination
    offset = (page - 1) * size
    assets = filtered_assets[offset:offset + size]
    
    # Calculate total pages
    total_pages = (total + size - 1) // size
    
    return MediaAssetList(
        assets=assets,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )

@router.get("/assets/{asset_id}", response_model=MediaAssetResponse)
async def get_media_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """Get a specific media asset by ID"""
    
    asset = MediaAssetStorage.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    
    # Check access permissions
    if not current_user.get("is_admin", False) and asset.get('uploaded_by') != current_user.get('id') and not asset.get('is_public', False):
        raise HTTPException(status_code=403, detail="Access denied to this media asset")
    
    # Increment view count
    asset['view_count'] = asset.get('view_count', 0) + 1
    MediaAssetStorage.update(asset_id, asset)
    
    return asset

@router.get("/assets/{asset_id}/download")
async def download_media_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """Download a media asset file"""
    
    asset = MediaAssetStorage.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    
    # Check access permissions
    if not current_user.get("is_admin", False) and asset.get('uploaded_by') != current_user.get('id') and not asset.get('is_public', False):
        raise HTTPException(status_code=403, detail="Access denied to this media asset")
    
    # Check if file exists
    if not os.path.exists(asset.get('file_path', '')):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Increment download count
    asset['download_count'] = asset.get('download_count', 0) + 1
    MediaAssetStorage.update(asset_id, asset)
    
    # Return file response
    return FileResponse(
        path=asset.get('file_path', ''),
        filename=asset.get('original_filename', ''),
        media_type=asset.get('mime_type', 'application/octet-stream')
    )

@router.put("/assets/{asset_id}", response_model=MediaAssetResponse)
async def update_media_asset(
    asset_id: int,
    asset_update: MediaAssetUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    """Update a media asset"""
    
    asset = MediaAssetStorage.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    
    # Check ownership or admin access
    if not current_user.get("is_admin", False) and asset.get('uploaded_by') != current_user.get('id'):
        raise HTTPException(status_code=403, detail="Only the owner or admin can update this asset")
    
    # Update fields
    update_data = asset_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        asset[field] = value
    
    asset['last_modified'] = datetime.utcnow().isoformat()
    updated_asset = MediaAssetStorage.update(asset_id, asset)
    
    logger.info(f"Updated media asset {asset_id} by user {current_user.get('id')}")
    
    return updated_asset

@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """Delete a media asset"""
    
    asset = MediaAssetStorage.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    
    # Check ownership or admin access
    if not current_user.get("is_admin", False) and asset.get('uploaded_by') != current_user.get('id'):
        raise HTTPException(status_code=403, detail="Only the owner or admin can delete this asset")
    
    # Delete file from disk
    delete_file_from_disk(asset.get('file_path', ''))
    
    # Delete database record
    MediaAssetStorage.delete(asset_id)
    
    logger.info(f"Deleted media asset {asset_id} by user {current_user.get('id')}")

@router.get("/stats", response_model=MediaAssetStats)
async def get_media_stats(
    pond_id: Optional[int] = Query(None, description="Filter by pond ID"),
    current_user: dict = Depends(get_current_active_user),
):
    """Get media asset statistics"""
    
    # Get all assets
    all_assets = MediaAssetStorage.get_all()
    
    # Apply pond filter if specified
    if pond_id:
        verify_pond_ownership(pond_id, current_user)
        all_assets = [asset for asset in all_assets if asset.get('pond_id') == pond_id]
    
    # Filter by visibility
    if not current_user.get("is_admin", False):
        all_assets = [asset for asset in all_assets 
                     if asset.get('uploaded_by') == current_user.get('id') or asset.get('is_public', False)]
    
    # Get basic stats
    total_assets = len(all_assets)
    total_size = sum(asset.get('file_size', 0) for asset in all_assets)
    
    # Get assets by type
    assets_by_type = {}
    for asset_type in ['image', 'video', 'document', 'audio']:
        count = len([asset for asset in all_assets if asset.get('file_type') == asset_type])
        if count > 0:
            assets_by_type[asset_type] = count
    
    # Get assets by category
    assets_by_category = {}
    for asset in all_assets:
        category = asset.get('category')
        if category:
            assets_by_category[category] = assets_by_category.get(category, 0) + 1
    
    # Get recent uploads (sort by upload_date)
    recent_uploads = sorted(all_assets, key=lambda x: x.get('upload_date', ''), reverse=True)[:10]
    
    # Get popular assets (sort by view_count)
    popular_assets = sorted(all_assets, key=lambda x: x.get('view_count', 0), reverse=True)[:10]
    
    return MediaAssetStats(
        total_assets=total_assets,
        total_size=total_size,
        assets_by_type=assets_by_type,
        assets_by_category=assets_by_category,
        recent_uploads=recent_uploads,
        popular_assets=popular_assets
    )

@router.post("/bulk", response_model=MediaAssetBulkResponse)
async def bulk_media_operations(
    bulk_data: MediaAssetBulk,
    current_user: dict = Depends(get_current_active_user),
):
    """Perform bulk operations on media assets"""
    
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only admins can perform bulk operations")
    
    # Get assets to operate on
    assets = []
    for asset_id in bulk_data.asset_ids:
        asset = MediaAssetStorage.get_by_id(asset_id)
        if asset:
            assets.append(asset)
    
    successful = 0
    failed = 0
    errors = []
    
    for asset in assets:
        try:
            if bulk_data.operation == 'delete':
                delete_file_from_disk(asset.get('file_path', ''))
                MediaAssetStorage.delete(asset.get('id'))
                successful += 1
                
            elif bulk_data.operation == 'make_public':
                asset['is_public'] = True
                MediaAssetStorage.update(asset.get('id'), asset)
                successful += 1
                
            elif bulk_data.operation == 'make_private':
                asset['is_public'] = False
                MediaAssetStorage.update(asset.get('id'), asset)
                successful += 1
                
            elif bulk_data.operation == 'update_category' and bulk_data.category:
                asset['category'] = bulk_data.category
                MediaAssetStorage.update(asset.get('id'), asset)
                successful += 1
                
            elif bulk_data.operation == 'add_tags' and bulk_data.tags:
                existing_tags = asset.get('tags', [])
                new_tags = [tag for tag in bulk_data.tags if tag not in existing_tags]
                asset['tags'] = existing_tags + new_tags
                MediaAssetStorage.update(asset.get('id'), asset)
                successful += 1
                
            elif bulk_data.operation == 'remove_tags' and bulk_data.tags:
                existing_tags = asset.get('tags', [])
                asset['tags'] = [tag for tag in existing_tags if tag not in bulk_data.tags]
                MediaAssetStorage.update(asset.get('id'), asset)
                successful += 1
                
        except Exception as e:
            failed += 1
            errors.append({
                "asset_id": asset.get('id'),
                "error": str(e)
            })
    
    logger.info(f"Bulk operation {bulk_data.operation}: {successful} successful, {failed} failed")
    
    return MediaAssetBulkResponse(
        operation=bulk_data.operation,
        total_processed=len(bulk_data.asset_ids),
        successful=successful,
        failed=failed,
        errors=errors
    )

@router.get("/search", response_model=MediaAssetSearchResponse)
async def search_media_assets(
    query: str = Query(..., min_length=2, description="Search query"),
    pond_id: Optional[int] = Query(None, description="Limit search to specific pond"),
    file_type: Optional[str] = Query(None, description="Limit search to specific file type"),
    include_private: bool = Query(False, description="Include private assets in search"),
    current_user: dict = Depends(get_current_active_user),
):
    """Search media assets by title, description, and tags"""
    
    import time
    start_time = time.time()
    
    # Get all assets
    all_assets = MediaAssetStorage.get_all()
    
    # Apply pond filter if specified
    if pond_id:
        verify_pond_ownership(pond_id, current_user)
        all_assets = [asset for asset in all_assets if asset.get('pond_id') == pond_id]
    
    # Apply file type filter if specified
    if file_type:
        all_assets = [asset for asset in all_assets if asset.get('file_type') == file_type]
    
    # Apply visibility filter
    if not include_private and not current_user.get("is_admin", False):
        all_assets = [asset for asset in all_assets 
                     if asset.get('uploaded_by') == current_user.get('id') or asset.get('is_public', False)]
    
    # Build search conditions
    search_terms = query.lower().split()
    results = []
    
    for asset in all_assets:
        # Check if asset matches any search term
        matches = False
        for term in search_terms:
            if (term in asset.get('title', '').lower() or 
                term in asset.get('description', '').lower() or
                any(term in tag.lower() for tag in asset.get('tags', []))):
                matches = True
                break
        
        if matches:
            results.append(asset)
    
    # Sort by upload_date (most recent first)
    results = sorted(results, key=lambda x: x.get('upload_date', ''), reverse=True)[:100]
    total_results = len(results)
    
    # Calculate search time
    search_time_ms = (time.time() - start_time) * 1000
    
    logger.info(f"Media search for '{query}': {total_results} results in {search_time_ms:.2f}ms")
    
    return MediaAssetSearchResponse(
        query=query,
        results=results,
        total_results=total_results,
        search_time_ms=search_time_ms
    )
