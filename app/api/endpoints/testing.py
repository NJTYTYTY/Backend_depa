"""
Testing API Endpoints

This module provides API endpoints for managing test requests, generating test data,
and executing test scenarios for the Backend_PWA system.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
import logging

from ...storage import UserStorage
from ...api.dependencies import get_current_user
from ...core.config import settings

# Import test utilities
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "tests" / "utils"))

try:
    from tests.utils.request_generator import (
        generate_sensor_data, generate_user_data, generate_pond_data,
        generate_media_asset_data, generate_bulk_operations,
        generate_comprehensive_test_suite, generate_stress_test_data,
        save_test_requests
    )
    from tests.utils.request_executor import TestRequestExecutor
    TEST_UTILS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Test utilities not available: {e}")
    TEST_UTILS_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testing", tags=["testing"])

# Configuration
TEST_DATA_DIR = Path("tests/test_data")
TEST_RESULTS_DIR = Path("tests/results")

def ensure_test_directories():
    """Ensure test directories exist"""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_test_data(
    test_type: str,
    count: int = 10,
    pond_id: Optional[int] = 1,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate test data for specified type
    
    Args:
        test_type: Type of test data to generate (sensor, user, pond, media, bulk)
        count: Number of test records to generate
        pond_id: ID of the pond (for sensor and media data)
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can generate test data
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can generate test data"
        )
    
    if not TEST_UTILS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test utilities are not available"
        )
    
    ensure_test_directories()
    
    try:
        if test_type == "sensor":
            data = generate_sensor_data(pond_id, count)
            filename = f"sensor_data_{count}_records.json"
            file_path = save_test_requests(filename, data, "sensor")
            
        elif test_type == "user":
            data = generate_user_data(count)
            filename = f"user_data_{count}_records.json"
            file_path = save_test_requests(filename, data, "user")
            
        elif test_type == "pond":
            data = generate_pond_data(count)
            filename = f"pond_data_{count}_records.json"
            file_path = save_test_requests(filename, data, "pond")
            
        elif test_type == "media":
            data = generate_media_asset_data(pond_id, count)
            filename = f"media_data_{count}_records.json"
            file_path = save_test_requests(filename, data, "media")
            
        elif test_type == "bulk":
            data = generate_bulk_operations(count)
            filename = f"bulk_operations_{count}_records.json"
            file_path = save_test_requests(filename, data, "bulk")
            
        elif test_type == "comprehensive":
            test_files = generate_comprehensive_test_suite(pond_id)
            return {
                "message": "Comprehensive test suite generated successfully",
                "test_files": test_files,
                "timestamp": datetime.now().isoformat()
            }
            
        elif test_type == "stress":
            data = generate_stress_test_data(pond_id, count)
            return {
                "message": f"Stress test data generated successfully",
                "file_path": data,
                "record_count": count,
                "timestamp": datetime.now().isoformat()
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported test type: {test_type}. Supported types: sensor, user, pond, media, bulk, comprehensive, stress"
            )
        
        logger.info(f"Generated {test_type} test data: {file_path}")
        
        return {
            "message": f"{test_type} test data generated successfully",
            "file_path": file_path,
            "record_count": count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating {test_type} test data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate {test_type} test data: {str(e)}"
        )

@router.post("/execute", status_code=status.HTTP_200_OK)
async def execute_test_requests(
    filename: str,
    test_type: str,
    base_url: str = "http://localhost:8000",
    auth_token: Optional[str] = None,
    delay: float = 0.1,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute test requests from a specified file
    
    Args:
        filename: Name of the test file to execute
        test_type: Type of test data
        base_url: Base URL of the API to test
        auth_token: Authentication token for protected endpoints
        delay: Delay between requests in seconds
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can execute test requests
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can execute test requests"
        )
    
    if not TEST_UTILS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test utilities are not available"
        )
    
    try:
        # Create test executor
        executor = TestRequestExecutor(base_url=base_url)
        
        # Execute test file
        results = await executor.execute_test_file(
            filename=filename,
            test_type=test_type,
            auth_token=auth_token,
            delay=delay
        )
        
        # Get performance summary
        summary = executor.get_performance_summary()
        
        # Save results
        results_file = executor.save_results()
        
        logger.info(f"Executed test file {filename}: {len(results)} requests")
        
        return {
            "message": f"Test execution completed successfully",
            "filename": filename,
            "test_type": test_type,
            "total_requests": len(results),
            "successful_requests": summary.get("successful_requests", 0),
            "failed_requests": summary.get("failed_requests", 0),
            "success_rate": summary.get("success_rate", 0),
            "results_file": results_file,
            "execution_time_stats": summary.get("execution_time_stats", {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test file not found: {filename}"
        )
    except Exception as e:
        logger.error(f"Error executing test requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute test requests: {str(e)}"
        )

@router.post("/execute-comprehensive", status_code=status.HTTP_200_OK)
async def execute_comprehensive_test_suite(
    base_url: str = "http://localhost:8000",
    auth_token: Optional[str] = None,
    delay: float = 0.1,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute the comprehensive test suite
    
    Args:
        base_url: Base URL of the API to test
        auth_token: Authentication token for protected endpoints
        delay: Delay between requests in seconds
        background_tasks: Background tasks for async execution
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can execute comprehensive tests
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can execute comprehensive test suites"
        )
    
    if not TEST_UTILS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test utilities are not available"
        )
    
    try:
        # Create test executor
        executor = TestRequestExecutor(base_url=base_url)
        
        # Execute comprehensive test suite
        results = await executor.execute_comprehensive_test_suite(
            auth_token=auth_token,
            delay=delay
        )
        
        # Get performance summary
        summary = executor.get_performance_summary()
        
        # Save results
        results_file = executor.save_results()
        
        logger.info("Comprehensive test suite execution completed")
        
        return {
            "message": "Comprehensive test suite execution completed successfully",
            "test_results": {
                test_type: {
                    "total_requests": len(test_results),
                    "successful_requests": sum(1 for r in test_results if r.get("success", False)),
                    "failed_requests": sum(1 for r in test_results if not r.get("success", False))
                }
                for test_type, test_results in results.items()
            },
            "overall_summary": summary,
            "results_file": results_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error executing comprehensive test suite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute comprehensive test suite: {str(e)}"
        )

@router.post("/execute-stress", status_code=status.HTTP_200_OK)
async def execute_stress_test(
    filename: str,
    base_url: str = "http://localhost:8000",
    auth_token: Optional[str] = None,
    max_concurrent: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute stress test with concurrent requests
    
    Args:
        filename: Name of the stress test file
        base_url: Base URL of the API to test
        auth_token: Authentication token for protected endpoints
        max_concurrent: Maximum concurrent requests
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can execute stress tests
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can execute stress tests"
        )
    
    if not TEST_UTILS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test utilities are not available"
        )
    
    try:
        # Create test executor
        executor = TestRequestExecutor(base_url=base_url)
        
        # Execute stress test
        results = await executor.execute_stress_test(
            filename=filename,
            auth_token=auth_token,
            max_concurrent=max_concurrent
        )
        
        # Get performance summary
        summary = executor.get_performance_summary()
        
        # Save results
        results_file = executor.save_results()
        
        logger.info(f"Stress test execution completed: {len(results)} requests")
        
        return {
            "message": "Stress test execution completed successfully",
            "filename": filename,
            "total_requests": len(results),
            "max_concurrent": max_concurrent,
            "successful_requests": summary.get("successful_requests", 0),
            "failed_requests": summary.get("failed_requests", 0),
            "success_rate": summary.get("success_rate", 0),
            "execution_time_stats": summary.get("execution_time_stats", {}),
            "results_file": results_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stress test file not found: {filename}"
        )
    except Exception as e:
        logger.error(f"Error executing stress test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute stress test: {str(e)}"
        )

@router.get("/files", status_code=status.HTTP_200_OK)
async def list_test_files(
    test_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List available test files
    
    Args:
        test_type: Filter by test type (optional)
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can list test files
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can list test files"
        )
    
    ensure_test_directories()
    
    try:
        test_files = {}
        
        if test_type:
            # List files for specific test type
            type_dir = TEST_DATA_DIR / test_type
            if type_dir.exists():
                files = [f.name for f in type_dir.iterdir() if f.is_file() and f.suffix == '.json']
                test_files[test_type] = files
        else:
            # List all test files by type
            for type_dir in TEST_DATA_DIR.iterdir():
                if type_dir.is_dir():
                    files = [f.name for f in type_dir.iterdir() if f.is_file() and f.suffix == '.json']
                    if files:
                        test_files[type_dir.name] = files
        
        return {
            "test_files": test_files,
            "total_types": len(test_files),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing test files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test files: {str(e)}"
        )

@router.get("/results", status_code=status.HTTP_200_OK)
async def list_test_results(
    current_user: dict = Depends(get_current_user),
):
    """
    List available test result files
    
    Args:
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can list test results
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can list test results"
        )
    
    ensure_test_directories()
    
    try:
        result_files = []
        
        if TEST_RESULTS_DIR.exists():
            for result_file in TEST_RESULTS_DIR.iterdir():
                if result_file.is_file() and result_file.suffix == '.json':
                    # Get file stats
                    stat = result_file.stat()
                    result_files.append({
                        "filename": result_file.name,
                        "size_bytes": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # Sort by modification time (newest first)
        result_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "test_results": result_files,
            "total_results": len(result_files),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing test results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test results: {str(e)}"
        )

@router.get("/results/{filename}", status_code=status.HTTP_200_OK)
async def get_test_result(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get test result details from a specific file
    
    Args:
        filename: Name of the test result file
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can view test results
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view test results"
        )
    
    ensure_test_directories()
    
    try:
        result_file = TEST_RESULTS_DIR / filename
        
        if not result_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test result file not found: {filename}"
            )
        
        # Load and return test results
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        return {
            "filename": filename,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in test result file: {filename}"
        )
    except Exception as e:
        logger.error(f"Error reading test result file {filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read test result file: {str(e)}"
        )

@router.delete("/files/{test_type}/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_file(
    test_type: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a test file
    
    Args:
        test_type: Type of test data
        filename: Name of the file to delete
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can delete test files
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete test files"
        )
    
    ensure_test_directories()
    
    try:
        file_path = TEST_DATA_DIR / test_type / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test file not found: {test_type}/{filename}"
            )
        
        # Delete the file
        file_path.unlink()
        
        logger.info(f"Deleted test file: {test_type}/{filename}")
        
    except Exception as e:
        logger.error(f"Error deleting test file {test_type}/{filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete test file: {str(e)}"
        )

@router.delete("/results/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_result(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a test result file
    
    Args:
        filename: Name of the result file to delete
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin users can delete test results
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete test results"
        )
    
    ensure_test_directories()
    
    try:
        result_file = TEST_RESULTS_DIR / filename
        
        if not result_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test result file not found: {filename}"
            )
        
        # Delete the file
        result_file.unlink()
        
        logger.info(f"Deleted test result file: {filename}")
        
    except Exception as e:
        logger.error(f"Error deleting test result file {filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete test result file: {str(e)}"
        )

@router.get("/health", status_code=status.HTTP_200_OK)
async def test_system_health(
    current_user: dict = Depends(get_current_user),
):
    """
    Check the health of the testing system
    
    Args:
        current_user: Current authenticated user
        db: Database session
    """
    try:
        health_status = {
            "status": "healthy",
            "test_utilities_available": TEST_UTILS_AVAILABLE,
            "test_data_directory": str(TEST_DATA_DIR),
            "test_results_directory": str(TEST_RESULTS_DIR),
            "directories_exist": {
                "test_data": TEST_DATA_DIR.exists(),
                "test_results": TEST_RESULTS_DIR.exists()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Check if test utilities are working
        if TEST_UTILS_AVAILABLE:
            try:
                # Test basic functionality
                test_data = generate_sensor_data(1, 1)
                health_status["test_generation_working"] = True
                health_status["sample_test_data"] = test_data[0] if test_data else None
            except Exception as e:
                health_status["test_generation_working"] = False
                health_status["test_generation_error"] = str(e)
        else:
            health_status["test_generation_working"] = False
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking testing system health: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
