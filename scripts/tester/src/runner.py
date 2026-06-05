# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3

import os, sys
import argparse
import json
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
import time
import concurrent.futures

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("service-tester")

@dataclass
class TestCase:
    """Represents a single test case for a service."""
    name: str
    endpoint: str
    method: str = "GET"
    headers: Dict[str, str] = None
    payload: Dict[str, Any] = None
    expected_status: int = 200
    expected_content: Optional[Dict[str, Any]] = None
    validation_func: Optional[Callable[[requests.Response], bool]] = None
    timeout: int = 10

@dataclass
class ServiceConfig:
    """Configuration for a service to be tested."""
    name: str
    base_url: str
    test_cases: List[TestCase]
    health_endpoint: str = "/health"

class ServiceTester:
    """Main class for testing services."""
    
    def __init__(self, services: List[ServiceConfig], parallel: bool = False):
        self.services = services
        self.parallel = parallel
        self.results = {}
    
    def run_test_case(self, service: ServiceConfig, test_case: TestCase) -> Dict[str, Any]:
        """Run a single test case against a service."""
        url = f"{service.base_url}{test_case.endpoint}"
        headers = test_case.headers or {}
        
        logger.info(f"Testing {service.name} - {test_case.name} at {url}")
        
        try:
            start_time = time.time()
            
            if test_case.method == "GET":
                response = requests.get(
                    url, 
                    headers=headers, 
                    timeout=test_case.timeout
                )
            elif test_case.method == "POST":
                response = requests.post(
                    url, 
                    json=test_case.payload, 
                    headers=headers, 
                    timeout=test_case.timeout
                )
            elif test_case.method == "PUT":
                response = requests.put(
                    url, 
                    json=test_case.payload, 
                    headers=headers, 
                    timeout=test_case.timeout
                )
            elif test_case.method == "DELETE":
                response = requests.delete(
                    url, 
                    headers=headers, 
                    timeout=test_case.timeout
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported method: {test_case.method}"
                }
                
            elapsed_time = time.time() - start_time
            
            # Check status code
            status_match = response.status_code == test_case.expected_status
            
            # Check content if expected_content is provided
            content_match = True
            if test_case.expected_content:
                try:
                    resp_json = response.json()
                    
                    # Type checking instead of exact value matching
                    for key, expected_value in test_case.expected_content.items():
                        if key not in resp_json:
                            logger.debug(f"Key '{key}' missing in response")
                            content_match = False
                            break
                        
                        actual_value = resp_json[key]
                        
                        # If expected_value is None, we only check that the key exists
                        if expected_value is None:
                            continue
                            
                        # Special handling for lists and dictionaries to check structure
                        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
                            # For nested dictionaries, you could implement recursive checking
                            # For now, we just check if it's a dictionary
                            continue
                            
                        if isinstance(expected_value, list) and isinstance(actual_value, list):
                            if expected_value:
                                if expected_value == actual_value:
                                    continue
                                else:
                                    logger.debug(f"List mismatch for key '{key}': expected {expected_value}, got {actual_value}")
                                    content_match = False
                                    break
                            else: # empty list
                                continue
                            
                        # For primitive types, check that types match
                        if not isinstance(actual_value, type(expected_value)):
                            logger.debug(f"Type mismatch for key '{key}': expected {type(expected_value)}, got {type(actual_value)}")
                            content_match = False
                            break
                            
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug(f"Error parsing response as JSON: {e}")
                    content_match = False
            
            # Run custom validation if provided
            validation_match = True
            if test_case.validation_func:
                validation_match = test_case.validation_func(response)
            
            success = status_match and content_match and validation_match
            
            return {
                "success": success,
                "status_code": response.status_code,
                "expected_status": test_case.expected_status,
                "status_match": status_match,
                "content_match": content_match,
                "validation_match": validation_match,
                "response_time": elapsed_time,
                "response_content": response.text[:1000] if not success else None  # Include truncated response on failure
            }
            
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def check_service_health(self, service: ServiceConfig) -> bool:
        """Check if a service is healthy before running tests."""
        if not service.health_endpoint:
            return True
            
        url = f"{service.base_url}{service.health_endpoint}"
        try:
            response = requests.get(url, timeout=5)
            return 200 <= response.status_code < 300
        except:
            return False
    
    def run_tests(self) -> Dict[str, Any]:
        """Run all test cases for all services."""
        for service in self.services:
            service_results = {
                "name": service.name,
                "base_url": service.base_url,
                "healthy": self.check_service_health(service),
                "test_cases": {}
            }
            
            if not service_results["healthy"]:
                logger.warning(f"Service {service.name} is not healthy. Skipping tests.")
                self.results[service.name] = service_results
                continue
            
            # Run test cases sequentially or in parallel
            if self.parallel:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(self.run_test_case, service, test_case): test_case
                        for test_case in service.test_cases
                    }
                    
                    for future in concurrent.futures.as_completed(futures):
                        test_case = futures[future]
                        service_results["test_cases"][test_case.name] = future.result()
            else:
                for test_case in service.test_cases:
                    service_results["test_cases"][test_case.name] = self.run_test_case(service, test_case)
            
            self.results[service.name] = service_results
        
        return self.results
    
    def print_summary(self):
        """Print a summary of test results."""
        total_tests = 0
        passed_tests = 0
        
        print("\n========== TEST RESULTS ==========")
        
        for service_name, service_results in self.results.items():
            print(f"\nService: {service_name} ({service_results['base_url']})")
            print(f"Health Check: {'PASSED' if service_results['healthy'] else 'FAILED'}")
            
            if not service_results["healthy"]:
                print("  Skipped all tests due to failed health check")
                continue
                
            service_total = len(service_results["test_cases"])
            service_passed = sum(1 for tc in service_results["test_cases"].values() if tc.get("success", False))
            
            total_tests += service_total
            passed_tests += service_passed
            
            print(f"Tests: {service_passed}/{service_total} passed")
            
            for tc_name, tc_result in service_results["test_cases"].items():
                status = "✅ PASSED" if tc_result.get("success", False) else "❌ FAILED"
                print(f"  {tc_name}: {status}")
                
                if not tc_result.get("success", False):
                    if "error" in tc_result:
                        print(f"    Error: {tc_result['error']}")
                    else:
                        if not tc_result.get("status_match", True):
                            print(f"    Status: Got {tc_result['status_code']}, expected {tc_result['expected_status']}")
                        if not tc_result.get("content_match", True):
                            print(f"    Content: Did not match expected content")
                        if not tc_result.get("validation_match", True):
                            print(f"    Validation: Custom validation failed")
        
        print("\n========== SUMMARY ==========")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.2f}%" if total_tests > 0 else 'N/A')
        
        return passed_tests == total_tests

def load_test_case(case_file):
    """Load test configuration from a JSON file."""
    logger.info(f"Loading test case from {case_file}")
    with open(case_file, 'r') as f:
        config = json.load(f)
    
    services = []
    for service_config in config["services"]:
        test_cases = []
        
        for tc in service_config["test_cases"]:
            # Create TestCase object
            test_case = TestCase(
                name=tc["name"],
                endpoint=tc["endpoint"],
                method=tc.get("method", "GET"),
                headers=tc.get("headers"),
                payload=tc.get("payload"),
                expected_status=tc.get("expected_status", 200),
                expected_content=tc.get("expected_content"),
                timeout=tc.get("timeout", 10)
            )
            test_cases.append(test_case)
        
        service = ServiceConfig(
            name=service_config["name"],
            base_url=service_config["base_url"],
            health_endpoint=service_config.get("health_endpoint", "/health"),
            test_cases=test_cases
        )
        services.append(service)
    
    return services

def main():
    parser = argparse.ArgumentParser(description="Test multiple services with defined test cases")
    parser.add_argument("--casebase", "-C", required=False, help="Dir to store test cases file(json)")
    parser.add_argument("--cases", "-c", required=False, help="Test case name to run")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress detailed output")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if args.quiet:
        logger.setLevel(logging.WARNING)
    
    # debug mode will override quiet mode
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if not args.casebase:
        args.casebase = os.path.join("cases")

    if not args.cases:
        args.cases = os.environ.get("CASES", "all.json")

    def _sanitize_case(case):
        case = case.strip()
        if not case.endswith(".json"):
            case = f"{case}.json"
        case = os.path.join(args.casebase, case)
        if not os.path.exists(case):
            logger.warning(f"case file {case} does not exist, skipped")
            return None
        return case

    cases = map(lambda x: _sanitize_case(x), args.cases.split(','))
    cases = list(filter(lambda x: x is not None, cases))
    
    all_passed = True
    for case in cases:
        try:
            services = load_test_case(case)
            tester = ServiceTester(services, parallel=args.parallel)
            results = tester.run_tests()
            
            if not args.quiet:
                tester.print_summary()
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
            
            # Exit with status code 0 if all tests passed, 1 otherwise
            all_passed = all_passed and all(
                all(tc.get("success", False) for tc in service_results["test_cases"].values())
                for service_name, service_results in results.items()
                if service_results["healthy"]
            )
        
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            all_passed = False

    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()