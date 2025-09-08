"""
Test Request Executor Utility

This module provides utilities for executing test JSON requests against
API endpoints to validate functionality and performance.
"""

import json
import asyncio
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestRequestExecutor:
    """
    Executes test requests against the API and provides detailed results
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize the test executor
        
        Args:
            base_url: Base URL of the API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.results: List[Dict[str, Any]] = []
        self.performance_stats: Dict[str, List[float]] = {}
        
    async def execute_single_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a single HTTP request
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            headers: Request headers
            params: Query parameters
        
        Returns:
            Dictionary containing request results
        """
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=headers, params=params)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=headers, params=params)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                execution_time = time.time() - start_time
                
                # Parse response
                try:
                    response_data = response.json() if response.content else None
                except json.JSONDecodeError:
                    response_data = response.text
                
                result = {
                    "method": method.upper(),
                    "endpoint": endpoint,
                    "url": url,
                    "status_code": response.status_code,
                    "execution_time": execution_time,
                    "request_data": data,
                    "request_headers": headers,
                    "request_params": params,
                    "response_data": response_data,
                    "response_headers": dict(response.headers),
                    "success": 200 <= response.status_code < 300,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Track performance
                if endpoint not in self.performance_stats:
                    self.performance_stats[endpoint] = []
                self.performance_stats[endpoint].append(execution_time)
                
                return result
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Request failed: {method} {endpoint} - {str(e)}")
            
            return {
                "method": method.upper(),
                "endpoint": endpoint,
                "url": url,
                "status_code": None,
                "execution_time": execution_time,
                "request_data": data,
                "request_headers": headers,
                "request_params": params,
                "response_data": None,
                "response_headers": {},
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def execute_test_file(
        self, 
        filename: str, 
        test_type: str = "general",
        auth_token: Optional[str] = None,
        delay: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Execute test requests from a JSON file
        
        Args:
            filename: Name of the test file
            test_type: Type of test data
            auth_token: Authentication token for protected endpoints
            delay: Delay between requests in seconds
        
        Returns:
            List of execution results
        """
        file_path = Path("tests/test_data") / test_type / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Test file not found: {file_path}")
        
        # Load test data
        with open(file_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        logger.info(f"Executing test file: {filename} ({len(test_data)} requests)")
        
        results = []
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        # Execute requests
        for i, item in enumerate(test_data):
            logger.info(f"Executing request {i+1}/{len(test_data)}: {item.get('endpoint', 'N/A')}")
            
            # Determine endpoint and method based on test type
            endpoint, method, request_data = self._prepare_request(item, test_type)
            
            result = await self.execute_single_request(
                method=method,
                endpoint=endpoint,
                data=request_data,
                headers=headers
            )
            
            results.append(result)
            self.results.append(result)
            
            # Add delay between requests
            if delay > 0 and i < len(test_data) - 1:
                await asyncio.sleep(delay)
        
        logger.info(f"Completed execution of {filename}: {len(results)} requests")
        return results
    
    def _prepare_request(self, item: Dict[str, Any], test_type: str) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        """
        Prepare request details based on test type and item data
        
        Args:
            item: Test item data
            test_type: Type of test data
        
        Returns:
            Tuple of (endpoint, method, request_data)
        """
        if test_type == "sensor":
            return "/api/v1/sensors/data", "POST", item
        elif test_type == "user":
            return "/api/v1/auth/register", "POST", item
        elif test_type == "pond":
            return "/api/v1/ponds", "POST", item
        elif test_type == "media":
            return "/api/v1/media/upload", "POST", item
        elif test_type == "bulk":
            return "/api/v1/media/bulk", "POST", item
        else:
            # Default fallback - assume it's a sensor data request
            return "/api/v1/sensors/data", "POST", item
    
    async def execute_comprehensive_test_suite(
        self, 
        auth_token: Optional[str] = None,
        delay: float = 0.1
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute the comprehensive test suite
        
        Args:
            auth_token: Authentication token
            delay: Delay between requests
        
        Returns:
            Dictionary mapping test type to results
        """
        logger.info("🚀 Starting comprehensive test suite execution...")
        
        test_suite = {
            "sensor": "sensor_data_comprehensive.json",
            "user": "user_data_comprehensive.json",
            "pond": "pond_data_comprehensive.json",
            "media": "media_data_comprehensive.json",
            "bulk": "bulk_operations_comprehensive.json"
        }
        
        results = {}
        
        for test_type, filename in test_suite.items():
            try:
                test_results = await self.execute_test_file(
                    filename=filename,
                    test_type=test_type,
                    auth_token=auth_token,
                    delay=delay
                )
                results[test_type] = test_results
                logger.info(f"✅ {test_type} tests completed: {len(test_results)} requests")
            except FileNotFoundError:
                logger.warning(f"⚠️ Test file not found for {test_type}: {filename}")
                results[test_type] = []
            except Exception as e:
                logger.error(f"❌ Error executing {test_type} tests: {str(e)}")
                results[test_type] = []
        
        logger.info("✅ Comprehensive test suite execution completed!")
        return results
    
    async def execute_stress_test(
        self, 
        filename: str,
        auth_token: Optional[str] = None,
        max_concurrent: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute stress test with concurrent requests
        
        Args:
            filename: Name of the stress test file
            auth_token: Authentication token
            max_concurrent: Maximum concurrent requests
        
        Returns:
            List of execution results
        """
        file_path = Path("tests/test_data/stress") / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Stress test file not found: {file_path}")
        
        # Load test data
        with open(file_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        logger.info(f"🔥 Starting stress test: {len(test_data)} requests, max {max_concurrent} concurrent")
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        # Execute requests with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(item):
            async with semaphore:
                endpoint, method, request_data = self._prepare_request(item, "sensor")
                return await self.execute_single_request(
                    method=method,
                    endpoint=endpoint,
                    data=request_data,
                    headers=headers
                )
        
        # Create tasks for all requests
        tasks = [execute_with_semaphore(item) for item in test_data]
        
        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Request {i+1} failed with exception: {str(result)}")
                processed_results.append({
                    "method": "POST",
                    "endpoint": "/api/v1/sensors/data",
                    "url": f"{self.base_url}/api/v1/sensors/data",
                    "status_code": None,
                    "execution_time": 0,
                    "request_data": test_data[i],
                    "request_headers": headers,
                    "request_params": None,
                    "response_data": None,
                    "response_headers": {},
                    "success": False,
                    "error": str(result),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                processed_results.append(result)
        
        total_time = time.time() - start_time
        logger.info(f"🔥 Stress test completed in {total_time:.2f}s: {len(processed_results)} requests")
        
        self.results.extend(processed_results)
        return processed_results
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary statistics
        
        Returns:
            Dictionary containing performance statistics
        """
        if not self.results:
            return {"message": "No results available"}
        
        # Overall statistics
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.get("success", False))
        failed_requests = total_requests - successful_requests
        
        # Execution time statistics
        execution_times = [r.get("execution_time", 0) for r in self.results if r.get("execution_time")]
        
        if execution_times:
            time_stats = {
                "min": min(execution_times),
                "max": max(execution_times),
                "mean": statistics.mean(execution_times),
                "median": statistics.median(execution_times),
                "std_dev": statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            }
        else:
            time_stats = {}
        
        # Status code distribution
        status_codes = {}
        for result in self.results:
            status = result.get("status_code")
            if status:
                status_codes[status] = status_codes.get(status, 0) + 1
        
        # Endpoint performance
        endpoint_stats = {}
        for endpoint, times in self.performance_stats.items():
            if times:
                endpoint_stats[endpoint] = {
                    "count": len(times),
                    "avg_time": statistics.mean(times),
                    "min_time": min(times),
                    "max_time": max(times)
                }
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "execution_time_stats": time_stats,
            "status_code_distribution": status_codes,
            "endpoint_performance": endpoint_stats
        }
    
    def save_results(self, filename: str = None) -> str:
        """
        Save test results to a JSON file
        
        Args:
            filename: Name of the file to save (auto-generated if None)
        
        Returns:
            Path to the saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results_{timestamp}.json"
        
        # Create results directory
        results_dir = Path("tests/results")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = results_dir / filename
        
        # Prepare results for saving
        save_data = {
            "test_execution": {
                "timestamp": datetime.now().isoformat(),
                "base_url": self.base_url,
                "total_requests": len(self.results)
            },
            "performance_summary": self.get_performance_summary(),
            "detailed_results": self.results
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✅ Test results saved to: {file_path}")
        return str(file_path)
    
    def print_summary(self):
        """
        Print a formatted summary of test results
        """
        if not self.results:
            print("📊 No test results available")
            return
        
        summary = self.get_performance_summary()
        
        print("\n" + "="*60)
        print("📊 TEST EXECUTION SUMMARY")
        print("="*60)
        
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        if 'execution_time_stats' in summary and summary['execution_time_stats']:
            time_stats = summary['execution_time_stats']
            print(f"\n⏱️ Execution Time Statistics:")
            print(f"  Min: {time_stats['min']:.3f}s")
            print(f"  Max: {time_stats['max']:.3f}s")
            print(f"  Mean: {time_stats['mean']:.3f}s")
            print(f"  Median: {time_stats['median']:.3f}s")
            print(f"  Std Dev: {time_stats['std_dev']:.3f}s")
        
        if 'status_code_distribution' in summary:
            print(f"\n📋 Status Code Distribution:")
            for status, count in summary['status_code_distribution'].items():
                print(f"  {status}: {count}")
        
        if 'endpoint_performance' in summary:
            print(f"\n🔗 Endpoint Performance:")
            for endpoint, stats in summary['endpoint_performance'].items():
                print(f"  {endpoint}:")
                print(f"    Count: {stats['count']}")
                print(f"    Avg Time: {stats['avg_time']:.3f}s")
                print(f"    Min Time: {stats['min_time']:.3f}s")
                print(f"    Max Time: {stats['max_time']:.3f}s")
        
        print("="*60)

async def execute_test_requests(
    filename: str, 
    base_url: str = "http://localhost:8000",
    auth_token: Optional[str] = None,
    delay: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Convenience function to execute test requests
    
    Args:
        filename: Name of the test file
        base_url: Base URL of the API
        auth_token: Authentication token
        delay: Delay between requests
    
    Returns:
        List of execution results
    """
    executor = TestRequestExecutor(base_url=base_url)
    
    # Determine test type from filename
    test_type = "general"
    if "sensor" in filename.lower():
        test_type = "sensor"
    elif "user" in filename.lower():
        test_type = "user"
    elif "pond" in filename.lower():
        test_type = "pond"
    elif "media" in filename.lower():
        test_type = "media"
    elif "bulk" in filename.lower():
        test_type = "bulk"
    
    results = await executor.execute_test_file(
        filename=filename,
        test_type=test_type,
        auth_token=auth_token,
        delay=delay
    )
    
    return results

if __name__ == "__main__":
    # Example usage
    async def main():
        print("🧪 Test Request Executor Utility")
        print("=" * 50)
        
        # Create executor
        executor = TestRequestExecutor(base_url="http://localhost:8000")
        
        # Execute comprehensive test suite
        print("🚀 Executing comprehensive test suite...")
        results = await executor.execute_comprehensive_test_suite(delay=0.1)
        
        # Print summary
        executor.print_summary()
        
        # Save results
        results_file = executor.save_results()
        print(f"\n💾 Results saved to: {results_file}")
    
    # Run the example
    asyncio.run(main())
