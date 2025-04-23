import requests
import time
import concurrent.futures
import json
import statistics
import os
import uuid  # Import uuid module if needed for unique request identifiers
import subprocess  # for running nvidia-smi
import threading  # concurrent monitoring
import re

# --- Configuration ---
TRANSFORM_ENDPOINT = "http://10.3.205.227:8752/transform"
STATUS_ENDPOINT_BASE = "http://10.3.205.227:8752/status/"
POLLING_INTERVAL = 0.5  # seconds
POLLING_TIMEOUT = 600  # seconds (10 minutes)
HEADERS = {
    "Content-Type": "application/json",
}
BASE_PAYLOAD = {
    "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf",
    "start_page": 1,
    "end_page": 1,
}
GPU_MONITOR_INTERVAL = 1  # seconds - How often to check VRAM


# --- GPU Monitoring Function ---
def monitor_gpu_vram(stop_event, vram_data, interval=1):
    """Monitors GPU VRAM usage using nvidia-smi in a separate thread."""
    print("GPU Monitor: Starting VRAM monitoring...")
    while not stop_event.is_set():
        try:
            # Execute nvidia-smi command
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            timestamp = time.time()

            # Parse the output (handles multiple GPUs, takes the first line for simplicity)
            # Output format: "used_mem1, total_mem1\nused_mem2, total_mem2\n..."
            lines = result.stdout.strip().split("\n")
            if lines:
                # Focus on the first GPU reported
                first_gpu_line = lines[0]
                used_mem_str, total_mem_str = first_gpu_line.split(",")
                used_mem_mib = int(used_mem_str.strip())
                total_mem_mib = int(total_mem_str.strip())
                vram_data.append(
                    {
                        "timestamp": timestamp,
                        "used_mib": used_mem_mib,
                        "total_mib": total_mem_mib,
                    }
                )
                # Optional: Print periodic VRAM usage
                # print(f"GPU Monitor: Used VRAM: {used_mem_mib} MiB / {total_mem_mib} MiB")
            else:
                print("GPU Monitor: No GPU data found in nvidia-smi output.")

        except FileNotFoundError:
            print(
                "GPU Monitor: Error: 'nvidia-smi' command not found. Cannot monitor GPU VRAM."
            )
            # Stop monitoring if nvidia-smi is not available
            break
        except subprocess.CalledProcessError as e:
            print(f"GPU Monitor: Error running nvidia-smi: {e}")
            # Optionally decide whether to continue or stop on error
            # break # Uncomment to stop monitoring on error
        except Exception as e:
            print(f"GPU Monitor: An unexpected error occurred during monitoring: {e}")
            # Optionally decide whether to continue or stop on error
            # break # Uncomment to stop monitoring on error

        # Wait for the specified interval or until stop_event is set
        stop_event.wait(interval)
    print("GPU Monitor: Stopping VRAM monitoring.")


def poll_status(status_url, task_id):
    """Polls the status endpoint until completion or timeout."""
    start_time = time.time()
    while True:
        current_time = time.time()
        if current_time - start_time > POLLING_TIMEOUT:
            print(f"Task {task_id}: Polling timed out after {POLLING_TIMEOUT} seconds.")
            return {"status": "timeout", "final_response": None}

        try:
            # print(f"Task {task_id}: Polling GET {status_url}") # Optional: More verbose logging
            response = requests.get(
                status_url, headers=HEADERS, timeout=10
            )  # Added timeout to GET
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # Handle potential empty response before JSON decoding
            if not response.text:
                print(f"Task {task_id}: Received empty response from status endpoint.")
                # Decide how to handle empty response, e.g., retry or fail
                time.sleep(POLLING_INTERVAL)
                continue  # Retry polling

            status_data = response.json()

            # Check if the response itself is null or empty dict before accessing keys
            if not status_data:
                print(
                    f"Task {task_id}: Received null or empty JSON response: {status_data}"
                )
                # Still polling, wait and continue
                time.sleep(POLLING_INTERVAL)
                continue

            status = status_data.get("msg")
            progress = status_data.get("progress", "N/A")
            current_step = status_data.get("current_step", "N/A")
            # est_remaining = status_data.get("estimated_remaining", "N/A") # Optional: match get_status_curl.sh

            # Only print significant updates or final status
            # Reduce frequency of polling status prints unless it's a final state
            # if status in ["success", "failed", "error"] or time.time() % 5 < POLLING_INTERVAL: # Print every ~5s or on final
            #     print(
            #         f"Task {task_id}: Polling Status - {status}, Progress: {progress}%, Step: {current_step}"
            #         # f", Est. Remaining: {est_remaining}s" # Optional
            #     )

            # Check for terminal states based on 'msg' field
            if status in ["success", "failed"]:
                print(f"Task {task_id}: Final status - {status}")
                return {"status": status, "final_response": status_data}
            elif status == "error":
                print(
                    f"Task {task_id}: Error status received - {status_data.get('error_message', 'Unknown error')}"
                )
                # Treat 'error' message as a failure for the stress test
                return {"status": "failed", "final_response": status_data}
            # If status is none of the above (e.g., 'processing', null, etc.), continue polling

        except requests.exceptions.Timeout:
            print(f"Task {task_id}: Timeout polling status URL {status_url}")
            # Decide if polling should continue or fail immediately
        except requests.exceptions.RequestException as e:
            print(f"Task {task_id}: Error polling status: {e}")
            # Decide if polling should continue or fail immediately
            # For now, let's retry after interval
        except json.JSONDecodeError as e:
            print(
                f"Task {task_id}: Error decoding status JSON: {e} - Response: {response.text}"
            )
            # Decide if polling should continue or fail, maybe retry a few times
            # For now, let's retry after interval

        time.sleep(POLLING_INTERVAL)


def execute_and_poll_task(request_id, payload):
    """Sends the initial POST request and polls for status using the UUID from the 'data' field."""
    task_start_time = time.time()
    task_uuid = None
    post_response = None  # Initialize
    try:
        # 1. Send initial POST request
        # print(f"Task {request_id}: Sending POST to {TRANSFORM_ENDPOINT}") # Reduce noise
        post_response = requests.post(
            TRANSFORM_ENDPOINT,
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        post_response.raise_for_status()  # Check for HTTP errors immediately

        # 2. Extract Task UUID from 'data' field
        response_data = post_response.json()
        task_uuid = response_data.get("data")

        if not task_uuid:
            print(
                f"Task {request_id}: Failed to get UUID from 'data' field in response: {response_data}"
            )
            return {
                "request_id": request_id,
                "total_time": time.time() - task_start_time,
                "success": False,
                "error": "UUID not found in 'data' field of response",
                "status_code": post_response.status_code,
                "final_status": "post_response_no_uuid",
                "post_response_body": response_data,  # Include response body for debugging
            }

        # print(f"Task {request_id}: Received UUID {task_uuid}") # Reduce noise
        status_url = f"{STATUS_ENDPOINT_BASE}{task_uuid}"

        # 3. Poll for status
        polling_result = poll_status(status_url, request_id)
        task_end_time = time.time()
        total_time = task_end_time - task_start_time

        return {
            "request_id": request_id,
            "uuid": task_uuid,
            "total_time": total_time,
            "success": polling_result["status"] == "success",
            "final_status": polling_result["status"],
            "final_response": polling_result["final_response"],
            "status_code": post_response.status_code,  # Initial POST status
        }

    except requests.exceptions.Timeout:
        task_end_time = time.time()
        return {
            "request_id": request_id,
            "uuid": task_uuid,  # Might be None
            "total_time": task_end_time - task_start_time,
            "success": False,
            "error": f"POST request to {TRANSFORM_ENDPOINT} timed out.",
            "status_code": "N/A",
            "final_status": "post_request_timeout",
        }
    except requests.exceptions.RequestException as e:
        task_end_time = time.time()
        return {
            "request_id": request_id,
            "uuid": task_uuid,  # Might be None if POST failed before getting UUID
            "total_time": task_end_time - task_start_time,
            "success": False,
            "error": str(e),
            "status_code": getattr(e.response, "status_code", "N/A"),
            "final_status": "post_request_failed",
        }
    except json.JSONDecodeError as e:
        task_end_time = time.time()
        # Ensure post_response exists before accessing its attributes
        status_code = post_response.status_code if post_response else "N/A"
        response_text = post_response.text if post_response else "N/A"
        return {
            "request_id": request_id,
            "uuid": None,
            "total_time": task_end_time - task_start_time,
            "success": False,
            "error": f"Failed to decode POST response JSON: {e}",
            "status_code": status_code,
            "final_status": "post_response_invalid_json",
            "post_response_text": response_text,  # Include raw text for debugging
        }
    except Exception as e:  # Catch any other unexpected errors
        task_end_time = time.time()
        status_code = post_response.status_code if post_response else "N/A"
        return {
            "request_id": request_id,
            "uuid": task_uuid,  # Might be None
            "total_time": task_end_time - task_start_time,
            "success": False,
            "error": f"An unexpected error occurred: {str(e)}",
            "status_code": status_code,  # Report status code if available
            "final_status": "unexpected_error",
        }


def stress_test(concurrent_request_num):
    all_results = []
    vram_readings = []  # List to store VRAM readings
    stop_monitoring_event = (
        threading.Event()
    )  # Event to signal monitoring thread to stop

    print(
        f"\nStarting stress test with {concurrent_request_num} concurrent requests..."
    )
    print(f"Target Endpoint: {TRANSFORM_ENDPOINT}")
    print(f"Status Endpoint Base: {STATUS_ENDPOINT_BASE}")
    print(f"Polling Interval: {POLLING_INTERVAL}s, Timeout: {POLLING_TIMEOUT}s")
    print(f"GPU VRAM Monitoring Interval: {GPU_MONITOR_INTERVAL}s")

    # Start GPU monitoring thread
    monitor_thread = threading.Thread(
        target=monitor_gpu_vram,
        args=(stop_monitoring_event, vram_readings, GPU_MONITOR_INTERVAL),
        daemon=True,  # Set as daemon so it exits if main thread exits unexpectedly
    )
    monitor_thread.start()

    start_overall_time = time.time()

    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrent_request_num
        ) as executor:
            # Store map of future to request_id for better error reporting
            future_to_req_id = {}
            for i in range(concurrent_request_num):
                # Customize payload per request if needed, e.g., different pages
                # current_payload = BASE_PAYLOAD.copy()
                # current_payload["start_page"] = i + 1
                # current_payload["end_page"] = i + 1
                current_payload = (
                    BASE_PAYLOAD  # Using the same payload for all requests for now
                )

                future = executor.submit(execute_and_poll_task, i, current_payload)
                future_to_req_id[future] = i

            for future in concurrent.futures.as_completed(future_to_req_id):
                req_id = future_to_req_id[future]
                try:
                    result = future.result()
                    all_results.append(result)
                    # Optional: Print progress as tasks complete
                    # print(f"Task {req_id} completed. Status: {result.get('final_status', 'N/A')}")
                except Exception as exc:
                    print(f"Request ID {req_id} generated an exception: {exc}")
                    all_results.append(
                        {
                            "request_id": req_id,
                            "total_time": "N/A",
                            "success": False,
                            "error": f"Future execution failed: {exc}",
                            "status_code": "N/A",
                            "final_status": "future_exception",
                        }
                    )
    finally:
        # Ensure monitoring thread is stopped regardless of exceptions
        print(
            "Stress test task submission complete. Waiting for tasks and stopping monitor..."
        )
        stop_monitoring_event.set()  # Signal the monitor thread to stop
        monitor_thread.join(
            timeout=GPU_MONITOR_INTERVAL * 2
        )  # Wait for monitor thread to finish
        if monitor_thread.is_alive():
            print("GPU Monitor: Warning - Monitor thread did not stop gracefully.")

    end_overall_time = time.time()
    print(
        f"\nStress test finished in {end_overall_time - start_overall_time:.2f} seconds."
    )

    # Sort results by request_id for easier reading of reports
    all_results.sort(key=lambda x: x.get("request_id", -1))

    # Pass VRAM readings to the report generator
    return generate_report(all_results, concurrent_request_num, vram_readings)


def generate_report(
    results, concurrent_request_num, vram_readings
):  # Added vram_readings
    total_tasks = len(results)
    success_count = sum(1 for result in results if result["success"])
    failure_count = total_tasks - success_count
    success_rate = (success_count / total_tasks) * 100 if total_tasks > 0 else 0

    valid_times = [
        result["total_time"]
        for result in results
        if isinstance(result.get("total_time"), (int, float)) and result["success"]
    ]

    # Calculate VRAM statistics
    vram_stats = {
        "Min Used (MiB)": "N/A",
        "Max Used (MiB)": "N/A",
        "Avg Used (MiB)": "N/A",
        "Total (MiB)": "N/A",
        "Readings": len(vram_readings),
    }
    if vram_readings:
        used_mibs = [r["used_mib"] for r in vram_readings]
        total_mibs = [
            r["total_mib"] for r in vram_readings
        ]  # Assuming total is constant, take first
        if used_mibs:
            vram_stats["Min Used (MiB)"] = min(used_mibs)
            vram_stats["Max Used (MiB)"] = max(used_mibs)
            vram_stats["Avg Used (MiB)"] = f"{statistics.mean(used_mibs):.0f}"
        if total_mibs:
            # Check if total memory was consistent
            if len(set(total_mibs)) == 1:
                vram_stats["Total (MiB)"] = total_mibs[0]
            else:
                vram_stats["Total (MiB)"] = "Multiple Values"  # Or handle differently

    report = {
        "Concurrent Requests": concurrent_request_num,
        "Total Tasks Attempted": total_tasks,
        "Successful Tasks": success_count,
        "Failed Tasks": failure_count,
        "Success Rate (%)": f"{success_rate:.1f}",
        "Task Completion Times (Successful Tasks)": {
            "Count": len(valid_times),
            "Average (s)": (
                f"{statistics.mean(valid_times):.2f}" if valid_times else "N/A"
            ),
            "Max (s)": f"{max(valid_times):.2f}" if valid_times else "N/A",
            "Min (s)": f"{min(valid_times):.2f}" if valid_times else "N/A",
            "Median (s)": (
                f"{statistics.median(valid_times):.2f}" if valid_times else "N/A"
            ),
            "Stdev (s)": (
                f"{statistics.stdev(valid_times):.2f}"
                if len(valid_times) > 1
                else "N/A"
            ),
        },
        "GPU VRAM Usage (MiB)": vram_stats,  # Added VRAM stats
        "Failure Details": [res for res in results if not res["success"]],
    }

    print_report(report)
    save_report(
        report, concurrent_request_num
    )  # Pass vram_readings if needed for raw data saving

    return report


def print_report(report):
    print("\n=== Stress Test Report ===")
    print(f"\nConcurrent Requests: {report['Concurrent Requests']}")
    print(f"Total Tasks Attempted: {report['Total Tasks Attempted']}")
    print(f"Successful Tasks: {report['Successful Tasks']}")
    print(f"Failed Tasks: {report['Failed Tasks']}")
    print(f"Success Rate: {report['Success Rate (%)']}%")

    print("\nTask Completion Times (Successful Tasks):")
    task_stats = report["Task Completion Times (Successful Tasks)"]
    for stat_name, stat_value in task_stats.items():
        print(f"  {stat_name}: {stat_value}")

    print("\nGPU VRAM Usage (MiB):")
    vram_stats = report.get("GPU VRAM Usage (MiB)", {})
    if vram_stats.get("Readings", 0) > 0:
        for stat_name, stat_value in vram_stats.items():
            print(f"  {stat_name}: {stat_value}")
    else:
        print(
            "  No VRAM readings collected (nvidia-smi might not be available or failed)."
        )

    if report["Failed Tasks"] > 0:
        print("\nFailure Details:")
        # Limit printing details to avoid flooding console
        max_failures_to_print = 10
        failures_printed = 0
        for failure in report["Failure Details"]:
            if failures_printed < max_failures_to_print:
                error_details = failure.get("error", "N/A")
                final_response = failure.get("final_response")
                if final_response:
                    error_details += (
                        f" | Final Response Msg: {final_response.get('msg', 'N/A')}"
                    )
                elif failure.get("post_response_body"):
                    error_details += (
                        f" | Post Response Body: {failure.get('post_response_body')}"
                    )
                elif failure.get("post_response_text"):
                    error_details += (
                        f" | Post Response Text: {failure.get('post_response_text')}"
                    )

                print(
                    f"  - Request ID: {failure.get('request_id', 'N/A')}, "
                    f"UUID: {failure.get('uuid', 'N/A')}, "
                    f"Status Code (POST): {failure.get('status_code', 'N/A')}, "
                    f"Final Status: {failure.get('final_status', 'N/A')}, "
                    f"Error: {error_details}"
                )
                failures_printed += 1
            else:
                print(
                    f"  ... (further {report['Failed Tasks'] - max_failures_to_print} failures not shown)"
                )
                break

    print("\n")


def save_report(
    report, concurrent_request_num
):  # Consider adding vram_readings to save raw data if needed
    # Ensure reports directory exists
    report_dir = "stress_test_reports"
    os.makedirs(report_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(
        report_dir, f"stress_test_report_{concurrent_request_num}_req_{timestamp}.md"
    )
    print(f"Saving report to {filename}")

    md_report = f"# Stress Test Report ({timestamp})\n\n"
    md_report += f"- **Concurrent Requests**: {report['Concurrent Requests']}\n"
    md_report += f"- **Total Tasks Attempted**: {report['Total Tasks Attempted']}\n"
    md_report += f"- **Successful Tasks**: {report['Successful Tasks']}\n"
    md_report += f"- **Failed Tasks**: {report['Failed Tasks']}\n"
    md_report += f"- **Success Rate**: {report['Success Rate (%)']}%\n\n"

    md_report += "## Task Completion Times (Successful Tasks)\n\n"
    task_stats = report["Task Completion Times (Successful Tasks)"]
    for stat_name, stat_value in task_stats.items():
        md_report += f"- **{stat_name}**: {stat_value}\n"
    md_report += "\n"

    # Add VRAM Stats to Markdown Report
    md_report += "## GPU VRAM Usage (MiB)\n\n"
    vram_stats = report.get("GPU VRAM Usage (MiB)", {})
    if vram_stats.get("Readings", 0) > 0:
        for stat_name, stat_value in vram_stats.items():
            md_report += f"- **{stat_name}**: {stat_value}\n"
    else:
        md_report += "- No VRAM readings collected (nvidia-smi might not be available or failed).\n"
    md_report += "\n"

    if report["Failed Tasks"] > 0:
        md_report += "## Failure Details\n\n"
        # Use a table for better readability in Markdown
        md_report += (
            "| Request ID | UUID | POST Status Code | Final Status | Error Details |\n"
        )
        md_report += "|---|---|---|---|---|\n"
        for failure in report["Failure Details"]:
            error_details = failure.get("error", "N/A")
            # Safely convert complex objects to string for Markdown
            final_response = failure.get("final_response")
            post_response_body = failure.get("post_response_body")
            post_response_text = failure.get("post_response_text")

            extra_info = ""
            # Limit length of extra info in markdown table
            max_len = 100
            if final_response:
                resp_str = json.dumps(final_response)
                extra_info = f"Final Response: `{resp_str[:max_len]}{'...' if len(resp_str) > max_len else ''}`"
            elif post_response_body:
                body_str = json.dumps(post_response_body)
                extra_info = f"Post Response Body: `{body_str[:max_len]}{'...' if len(body_str) > max_len else ''}`"
            elif post_response_text:
                extra_info = f"Post Response Text: `{post_response_text[:max_len]}{'...' if len(post_response_text) > max_len else ''}`"

            full_error = f"`{error_details}` {extra_info}".strip()
            # Escape pipe characters within the error message for Markdown table
            full_error = full_error.replace("|", "\\|")

            md_report += (
                f"| {failure.get('request_id', 'N/A')} | "
                f"`{failure.get('uuid', 'N/A')}` | "
                f"{failure.get('status_code', 'N/A')} | "
                f"{failure.get('final_status', 'N/A')} | "
                f"{full_error} |\n"
            )

    with open(filename, "w") as md_file:
        md_file.write(md_report)


if __name__ == "__main__":
    # Number of concurrent requests to simulate
    concurrent_request_num = 10
    if len(os.sys.argv) > 1:
        try:
            concurrent_request_num = int(os.sys.argv[1])
            print(
                f"Running with {concurrent_request_num} concurrent requests from command line argument."
            )
        except ValueError:
            print(
                f"Invalid argument: {os.sys.argv[1]}. Using default: {concurrent_request_num}"
            )

    stress_test(concurrent_request_num)
