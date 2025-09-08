"""
Pydantic schemas for Backend_PWA
"""

from .auth import (
    UserBase, UserCreate, UserLogin, UserResponse, Token, TokenData,
    TokenRefresh, UserUpdate, PasswordChange, UserStatusUpdate, UserRoleUpdate
)
from .pond import (
    PondCreate, PondUpdate, PondResponse, PondList, PondFilter,
    PondStats, PondDetail
)
from .sensor import (
    SensorDataCreate, SensorDataUpdate, SensorDataResponse, SensorDataList,
    SensorDataFilter, SensorDataAggregation, SensorDataLatest, SensorDataWebhook,
    SensorThreshold, SensorThresholdResponse, SensorDataBulk, SensorDataBulkResponse
)
from .media import (
    MediaAssetBase, MediaAssetCreate, MediaAssetUpdate, MediaAssetResponse, 
    MediaAssetList, MediaAssetFilter, MediaAssetUpload, MediaAssetStats,
    MediaAssetBulk, MediaAssetBulkResponse, MediaAssetSearch, MediaAssetSearchResponse
)
from .insight import InsightCreate, InsightResponse, InsightList
from .control import ControlActionCreate, ControlLogResponse, ControlLogList

__all__ = [
    "UserBase", "UserCreate", "UserLogin", "UserResponse", "Token", "TokenData",
    "TokenRefresh", "UserUpdate", "PasswordChange", "UserStatusUpdate", "UserRoleUpdate",
    "PondCreate", "PondUpdate", "PondResponse", "PondList", "PondFilter", "PondStats", "PondDetail",
    "SensorDataCreate", "SensorDataUpdate", "SensorDataResponse", "SensorDataList",
    "SensorDataFilter", "SensorDataAggregation", "SensorDataLatest", "SensorDataWebhook",
    "SensorThreshold", "SensorThresholdResponse", "SensorDataBulk", "SensorDataBulkResponse",
    "MediaAssetBase", "MediaAssetCreate", "MediaAssetUpdate", "MediaAssetResponse", 
    "MediaAssetList", "MediaAssetFilter", "MediaAssetUpload", "MediaAssetStats",
    "MediaAssetBulk", "MediaAssetBulkResponse", "MediaAssetSearch", "MediaAssetSearchResponse",
    "InsightCreate", "InsightResponse", "InsightList",
    "ControlActionCreate", "ControlLogResponse", "ControlLogList",
]
