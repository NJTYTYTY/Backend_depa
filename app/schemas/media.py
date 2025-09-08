"""
Media Asset Management Schemas
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime
import re

class MediaAssetBase(BaseModel):
    """Base schema for media assets"""
    title: str = Field(..., min_length=1, max_length=255, description="Title of the media asset")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the media asset")
    file_type: Literal['image', 'video', 'document', 'audio'] = Field(..., description="Type of media file")
    file_extension: str = Field(..., description="File extension (e.g., jpg, mp4, pdf)")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorizing the asset")
    is_public: bool = Field(default=False, description="Whether the asset is publicly accessible")
    category: Optional[str] = Field(None, max_length=100, description="Category of the media asset")

class MediaAssetCreate(MediaAssetBase):
    """Schema for creating a new media asset"""
    pond_id: int = Field(..., description="ID of the pond this asset belongs to")
    file_path: str = Field(..., description="Path to the stored file")
    original_filename: str = Field(..., description="Original filename from upload")
    uploaded_by: int = Field(..., description="ID of the user who uploaded the asset")
    
    @validator('file_extension')
    def validate_file_extension(cls, v):
        """Validate file extension format"""
        if not re.match(r'^[a-zA-Z0-9]{1,10}$', v):
            raise ValueError('File extension must be alphanumeric and 1-10 characters')
        return v.lower()
    
    @validator('file_size')
    def validate_file_size(cls, v):
        """Validate file size (max 100MB)"""
        max_size = 100 * 1024 * 1024  # 100MB
        if v > max_size:
            raise ValueError(f'File size must be less than 100MB, got {v} bytes')
        return v
    
    @validator('mime_type')
    def validate_mime_type(cls, v):
        """Validate MIME type format"""
        if not re.match(r'^[a-zA-Z0-9\-\.]+\/[a-zA-Z0-9\-\.]+$', v):
            raise ValueError('Invalid MIME type format')
        return v

class MediaAssetUpdate(BaseModel):
    """Schema for updating a media asset"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    category: Optional[str] = Field(None, max_length=100)
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        return v

class MediaAssetResponse(MediaAssetBase):
    """Schema for media asset responses"""
    id: int
    pond_id: int
    file_path: str
    original_filename: str
    uploaded_by: int
    upload_date: datetime
    last_modified: datetime
    download_count: int = Field(default=0, description="Number of times the asset was downloaded")
    view_count: int = Field(default=0, description="Number of times the asset was viewed")
    
    class Config:
        from_attributes = True

class MediaAssetList(BaseModel):
    """Schema for listing media assets with pagination"""
    assets: List[MediaAssetResponse]
    total: int
    page: int
    size: int
    total_pages: int

class MediaAssetFilter(BaseModel):
    """Schema for filtering media assets"""
    pond_id: Optional[int] = Field(None, description="Filter by pond ID")
    file_type: Optional[Literal['image', 'video', 'document', 'audio']] = Field(None, description="Filter by file type")
    uploaded_by: Optional[int] = Field(None, description="Filter by uploader user ID")
    is_public: Optional[bool] = Field(None, description="Filter by public/private status")
    category: Optional[str] = Field(None, description="Filter by category")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (any of the specified tags)")
    start_date: Optional[datetime] = Field(None, description="Filter by upload date range (start)")
    end_date: Optional[datetime] = Field(None, description="Filter by upload date range (end)")
    min_file_size: Optional[int] = Field(None, gt=0, description="Minimum file size in bytes")
    max_file_size: Optional[int] = Field(None, gt=0, description="Maximum file size in bytes")
    
    @validator('start_date', 'end_date')
    def validate_date_range(cls, v, values):
        """Validate date range"""
        if 'start_date' in values and 'end_date' in values:
            if values['start_date'] and values['end_date']:
                if values['start_date'] >= values['end_date']:
                    raise ValueError('Start date must be before end date')
        return v
    
    @validator('min_file_size', 'max_file_size')
    def validate_file_size_range(cls, v, values):
        """Validate file size range"""
        if 'min_file_size' in values and 'max_file_size' in values:
            if values['min_file_size'] and values['max_file_size']:
                if values['min_file_size'] >= values['max_file_size']:
                    raise ValueError('Min file size must be less than max file size')
        return v

class MediaAssetUpload(BaseModel):
    """Schema for file upload requests"""
    pond_id: int = Field(..., description="ID of the pond to upload to")
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(default_factory=list)
    is_public: bool = Field(default=False)
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags"""
        if v:
            # Remove duplicates and empty tags
            v = [tag.strip() for tag in v if tag.strip()]
            # Limit number of tags
            if len(v) > 10:
                raise ValueError('Maximum 10 tags allowed')
        return v

class MediaAssetStats(BaseModel):
    """Schema for media asset statistics"""
    total_assets: int
    total_size: int  # in bytes
    assets_by_type: dict  # file_type -> count
    assets_by_category: dict  # category -> count
    recent_uploads: List[MediaAssetResponse]  # last 10 uploads
    popular_assets: List[MediaAssetResponse]  # top 10 by view count

class MediaAssetBulk(BaseModel):
    """Schema for bulk media asset operations"""
    asset_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of asset IDs to operate on")
    operation: Literal['delete', 'make_public', 'make_private', 'update_category', 'add_tags', 'remove_tags'] = Field(..., description="Bulk operation to perform")
    category: Optional[str] = Field(None, description="New category for update_category operation")
    tags: Optional[List[str]] = Field(None, description="Tags for add_tags/remove_tags operations")
    
    @validator('asset_ids')
    def validate_asset_ids(cls, v):
        """Validate asset IDs"""
        if len(set(v)) != len(v):
            raise ValueError('Duplicate asset IDs are not allowed')
        return v

class MediaAssetBulkResponse(BaseModel):
    """Schema for bulk operation responses"""
    operation: str
    total_processed: int
    successful: int
    failed: int
    errors: List[dict] = Field(default_factory=list, description="List of errors for failed operations")

class MediaAssetSearch(BaseModel):
    """Schema for media asset search"""
    query: str = Field(..., min_length=1, max_length=255, description="Search query")
    pond_id: Optional[int] = Field(None, description="Limit search to specific pond")
    file_type: Optional[Literal['image', 'video', 'document', 'audio']] = Field(None, description="Limit search to specific file type")
    include_private: bool = Field(default=False, description="Include private assets in search")
    
    @validator('query')
    def validate_query(cls, v):
        """Validate search query"""
        if len(v.strip()) < 2:
            raise ValueError('Search query must be at least 2 characters long')
        return v.strip()

class MediaAssetSearchResponse(BaseModel):
    """Schema for search results"""
    query: str
    results: List[MediaAssetResponse]
    total_results: int
    search_time_ms: float  # Search execution time in milliseconds
