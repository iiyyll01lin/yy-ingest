import os
import subprocess
import time
import json
import pandas as pd
import numpy as np
import matplotlib

# Set the backend to a non-interactive one for server environments
matplotlib.use("Agg")  # This must come before importing pyplot
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from tabulate import tabulate
import re
import shutil  # For copying files

# Test matrix - different combinations to try
PDF_SEMAPHORE_VALUES = [1, 2, 4, 8]
IMG_DESC_SEMAPHORE_VALUES = [1, 2, 4, 8, 16]
CONCURRENT_REQUESTS = [4, 8, 16]

# Create timestamp for this test run
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_DIR = f"semaphore_optimization_{TIMESTAMP}"
os.makedirs(REPORT_DIR, exist_ok=True)

# Create a dedicated images directory for easier access
IMAGES_DIR = os.path.join(REPORT_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
print(f"Images will be saved to: {IMAGES_DIR}")

# Track results across all tests
results_tracker = {
    "pdf_sem": [],
    "img_sem": [],
    "concurrency": [],
    "success_rate": [],
    "avg_time": [],
    "max_vram_usage": [],
    "report_path": [],
    "test_runtime": [],  # Add runtime tracking
}


def format_time(seconds):
    """Format seconds into hours, minutes, seconds"""
    return str(timedelta(seconds=int(seconds)))


def print_progress(
    current, total, pdf_sem, img_sem, concurrency, elapsed_time=0, eta=None
):
    """Print progress information with percentage complete and ETA"""
    percent = (current / total) * 100
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)

    # Basic progress
    progress_str = f"\r[{bar}] {percent:.1f}% | Test {current}/{total} | PDF={pdf_sem}, IMG={img_sem}, CONC={concurrency}"

    # Add timing information
    if elapsed_time > 0:
        progress_str += f" | Elapsed: {format_time(elapsed_time)}"

    if eta:
        progress_str += f" | ETA: {format_time(eta)}"

    print(progress_str, end="")
    if current == total:
        print()  # Add newline when complete


def extract_metrics_from_report(report_path):
    """Extract key metrics from a test report file"""
    try:
        with open(report_path, "r") as f:
            content = f.read()

        # Extract success rate
        success_rate_match = re.search(r"Success Rate.*?(\d+\.\d+)%", content)
        success_rate = float(success_rate_match.group(1)) if success_rate_match else 0

        # Extract average time
        avg_time_match = re.search(r"Average \(s\).*?(\d+\.\d+)", content)
        avg_time = float(avg_time_match.group(1)) if avg_time_match else 999

        # Extract max VRAM usage across all GPUs
        max_vram_usage = 0
        vram_matches = re.findall(r"Max Used \(MiB\).*?(\d+)", content)
        if vram_matches:
            max_vram_usage = max([int(v) for v in vram_matches])

        return success_rate, avg_time, max_vram_usage
    except Exception as e:
        print(f"Error extracting metrics from {report_path}: {e}")
        return 0, 999, 0


def create_matrix_report():
    """Create a consolidated matrix report of all test results"""
    # Convert results to DataFrames for easier manipulation
    df = pd.DataFrame(results_tracker)

    print("\nGenerating final optimization report...")

    # Create matrix tables for each key metric
    reports = []

    # Runtime Statistics
    reports.append("## Runtime Statistics")
    reports.append(f"- Total test combinations: {len(df)}")
    reports.append(f"- Total runtime: {format_time(df['test_runtime'].sum())}")
    reports.append(f"- Average test runtime: {format_time(df['test_runtime'].mean())}")
    reports.append(f"- Fastest test: {format_time(df['test_runtime'].min())}")
    reports.append(f"- Slowest test: {format_time(df['test_runtime'].max())}")
    reports.append("")

    # 1. Success Rate Matrix
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if not filtered.empty:
            pivot = filtered.pivot(
                index="pdf_sem", columns="img_sem", values="success_rate"
            )
            reports.append(f"\n## Success Rate (%) - Concurrency: {concurrency}")
            reports.append(
                tabulate(pivot, headers="keys", tablefmt="github", floatfmt=".1f")
            )

    # 2. Average Time Matrix
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if not filtered.empty:
            pivot = filtered.pivot(
                index="pdf_sem", columns="img_sem", values="avg_time"
            )
            reports.append(
                f"\n## Average Processing Time (s) - Concurrency: {concurrency}"
            )
            reports.append(
                tabulate(pivot, headers="keys", tablefmt="github", floatfmt=".2f")
            )

    # 3. Max VRAM Usage Matrix
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if not filtered.empty:
            pivot = filtered.pivot(
                index="pdf_sem", columns="img_sem", values="max_vram_usage"
            )
            reports.append(f"\n## Max VRAM Usage (MiB) - Concurrency: {concurrency}")
            reports.append(tabulate(pivot, headers="keys", tablefmt="github"))

    # 4. Test Runtime Matrix
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if not filtered.empty:
            pivot = filtered.pivot(
                index="pdf_sem", columns="img_sem", values="test_runtime"
            )
            reports.append(f"\n## Test Runtime (s) - Concurrency: {concurrency}")
            reports.append(
                tabulate(pivot, headers="keys", tablefmt="github", floatfmt=".0f")
            )

    # Find optimal configurations based on success rate and speed
    # Filter for 100% success rate or at least 95%
    successful = df[df["success_rate"] >= 95].copy()
    if successful.empty:
        # If no 95%+ success rates, use top 25% performers
        threshold = np.percentile(df["success_rate"], 75)
        successful = df[df["success_rate"] >= threshold].copy()

    # Sort by average time (ascending)
    successful.sort_values("avg_time", inplace=True)

    reports.append("\n## Optimal Configurations (Sorted by Speed)")
    reports.append(
        "Configurations with highest success rates, sorted by processing speed:"
    )

    top_results = []
    for i, row in successful.head(5).iterrows():
        top_results.append(
            {
                "Rank": i + 1,
                "PDF Semaphore": row["pdf_sem"],
                "IMG Semaphore": row["img_sem"],
                "Concurrency": row["concurrency"],
                "Success Rate (%)": f"{row['success_rate']:.1f}",
                "Avg Time (s)": f"{row['avg_time']:.2f}",
                "Max VRAM (MiB)": row["max_vram_usage"],
                "Test Runtime": format_time(row["test_runtime"]),
            }
        )

    reports.append(tabulate(top_results, headers="keys", tablefmt="github"))

    # Create final recommendation
    if successful.empty:
        recommendation = "No clear optimal configuration found. All tests had issues."
    else:
        best = successful.iloc[0]
        recommendation = (
            f"**RECOMMENDED CONFIGURATION:**\n"
            f"- PDF_PROCESSOR_SEMAPHORE={best['pdf_sem']}\n"
            f"- IMG_DESC_SEMAPHORE={best['img_sem']}\n"
            f"- Handles {best['concurrency']} concurrent requests with "
            f"{best['success_rate']:.1f}% success rate and {best['avg_time']:.2f}s average processing time"
        )

    reports.append(f"\n## Recommendation\n{recommendation}")

    # Also create a visualization
    try:
        created_images = create_visualizations(df)

        # Add image section to report
        if created_images:
            reports.append("\n## Visualizations\n")
            reports.append("Click the links below to view the visualization images:")

            for title, filename in created_images:
                # Use relative paths to make it easier to view on server
                reports.append(f"\n### {title}")
                reports.append(f"![{title}](images/{filename})")
                reports.append(f"\n[View full size](images/{filename})\n")
    except Exception as e:
        print(f"Error creating visualizations: {e}")
        reports.append("\n## Visualizations\nError creating visualizations.")

    # Write complete report
    report_path = os.path.join(REPORT_DIR, "semaphore_optimization_report.md")
    with open(report_path, "w") as f:
        f.write("# Semaphore Optimization Report\n\n")
        f.write(f"Test Run: {TIMESTAMP}\n\n")
        f.write(
            "This report compares different combinations of PDF_PROCESSOR_SEMAPHORE and IMG_DESC_SEMAPHORE values "
            "to find the optimal configuration for throughput and stability.\n\n"
        )
        f.write("All images can be found in the `images/` directory.\n\n")
        f.write("\n".join(reports))

    # Create a simple HTML version for easier viewing
    html_path = os.path.join(REPORT_DIR, "semaphore_optimization_report.html")
    try:
        import markdown

        with open(report_path, "r") as f:
            md_content = f.read()

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Semaphore Optimization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                img {{ max-width: 800px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            {markdown.markdown(md_content, extensions=['tables'])}
        </body>
        </html>
        """

        with open(html_path, "w") as f:
            f.write(html_content)

        print(f"HTML report created: {html_path}")
    except ImportError:
        print(
            "Python 'markdown' package not installed. Skipping HTML report generation."
        )
    except Exception as e:
        print(f"Error creating HTML report: {e}")

    print(f"\nFinal optimization report created: {report_path}")


def create_visualizations(df):
    """Create visualizations of the test results"""
    # Create a directory for visualizations
    viz_dir = os.path.join(REPORT_DIR, "visualizations")
    os.makedirs(viz_dir, exist_ok=True)

    # Track all created images to include in report
    created_images = []

    # For each concurrency level, create a heatmap of success rates
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if filtered.empty:
            continue

        pivot = filtered.pivot(
            index="pdf_sem", columns="img_sem", values="success_rate"
        )

        plt.figure(figsize=(10, 7))
        heatmap = plt.imshow(pivot, cmap="RdYlGn")
        plt.colorbar(heatmap, label="Success Rate (%)")

        # Add labels
        plt.title(f"Success Rate by Semaphore Values (Concurrency: {concurrency})")
        plt.xlabel("IMG_DESC_SEMAPHORE")
        plt.ylabel("PDF_PROCESSOR_SEMAPHORE")

        # X and Y ticks
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)

        # Add text annotations
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.iloc[i, j]
                if not np.isnan(value):
                    plt.text(
                        j,
                        i,
                        f"{value:.1f}%",
                        ha="center",
                        va="center",
                        color="black" if value > 50 else "white",
                    )

        plt.tight_layout()

        # Save to both locations
        original_path = os.path.join(
            viz_dir, f"success_rate_heatmap_conc{concurrency}.png"
        )
        plt.savefig(original_path)

        # Save/copy to images directory
        img_filename = f"success_rate_heatmap_conc{concurrency}.png"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        plt.savefig(img_path)
        created_images.append(
            (f"Success Rate (Concurrency: {concurrency})", img_filename)
        )

        plt.close()

    # Create average time heatmaps
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if filtered.empty:
            continue

        pivot = filtered.pivot(index="pdf_sem", columns="img_sem", values="avg_time")

        plt.figure(figsize=(10, 7))
        # Use a reverse colormap (blue is good/fast, red is bad/slow)
        heatmap = plt.imshow(pivot, cmap="RdYlBu_r")
        plt.colorbar(heatmap, label="Average Time (s)")

        # Add labels
        plt.title(
            f"Average Processing Time by Semaphore Values (Concurrency: {concurrency})"
        )
        plt.xlabel("IMG_DESC_SEMAPHORE")
        plt.ylabel("PDF_PROCESSOR_SEMAPHORE")

        # X and Y ticks
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)

        # Add text annotations
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.iloc[i, j]
                if not np.isnan(value):
                    plt.text(
                        j,
                        i,
                        f"{value:.2f}s",
                        ha="center",
                        va="center",
                        color="white" if value > 100 else "black",
                    )

        plt.tight_layout()

        # Save to both locations
        original_path = os.path.join(viz_dir, f"avg_time_heatmap_conc{concurrency}.png")
        plt.savefig(original_path)

        # Save/copy to images directory
        img_filename = f"avg_time_heatmap_conc{concurrency}.png"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        plt.savefig(img_path)
        created_images.append(
            (f"Average Time (Concurrency: {concurrency})", img_filename)
        )

        plt.close()

    # Create VRAM usage heatmaps
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if filtered.empty:
            continue

        pivot = filtered.pivot(
            index="pdf_sem", columns="img_sem", values="max_vram_usage"
        )

        plt.figure(figsize=(10, 7))
        heatmap = plt.imshow(pivot, cmap="YlOrRd")
        plt.colorbar(heatmap, label="Max VRAM Usage (MiB)")

        # Add labels
        plt.title(f"Max VRAM Usage by Semaphore Values (Concurrency: {concurrency})")
        plt.xlabel("IMG_DESC_SEMAPHORE")
        plt.ylabel("PDF_PROCESSOR_SEMAPHORE")

        # X and Y ticks
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)

        # Add text annotations
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.iloc[i, j]
                if not np.isnan(value):
                    plt.text(
                        j,
                        i,
                        f"{int(value)}MB",
                        ha="center",
                        va="center",
                        color="white" if value > 15000 else "black",
                    )

        plt.tight_layout()

        # Save to both locations
        original_path = os.path.join(
            viz_dir, f"vram_usage_heatmap_conc{concurrency}.png"
        )
        plt.savefig(original_path)

        # Save/copy to images directory
        img_filename = f"vram_usage_heatmap_conc{concurrency}.png"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        plt.savefig(img_path)
        created_images.append(
            (f"VRAM Usage (Concurrency: {concurrency})", img_filename)
        )

        plt.close()

    # Add a runtime heatmap visualization
    for concurrency in CONCURRENT_REQUESTS:
        filtered = df[df["concurrency"] == concurrency]
        if filtered.empty:
            continue

        pivot = filtered.pivot(
            index="pdf_sem", columns="img_sem", values="test_runtime"
        )

        plt.figure(figsize=(10, 7))
        heatmap = plt.imshow(pivot, cmap="YlOrRd")
        plt.colorbar(heatmap, label="Test Runtime (seconds)")

        # Add labels
        plt.title(f"Test Runtime by Semaphore Values (Concurrency: {concurrency})")
        plt.xlabel("IMG_DESC_SEMAPHORE")
        plt.ylabel("PDF_PROCESSOR_SEMAPHORE")

        # X and Y ticks
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)

        # Add text annotations
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.iloc[i, j]
                if not np.isnan(value):
                    plt.text(
                        j,
                        i,
                        f"{int(value)}s",
                        ha="center",
                        va="center",
                        color="white" if value > 120 else "black",
                    )

        plt.tight_layout()

        # Save to images directory
        img_filename = f"test_runtime_heatmap_conc{concurrency}.png"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        plt.savefig(img_path)
        created_images.append(
            (f"Test Runtime (Concurrency: {concurrency})", img_filename)
        )

        plt.close()

    return created_images


def main():
    total_tests = (
        len(PDF_SEMAPHORE_VALUES)
        * len(IMG_DESC_SEMAPHORE_VALUES)
        * len(CONCURRENT_REQUESTS)
    )
    current_test = 0

    # Timing variables
    start_time_total = time.time()
    test_times = []
    estimated_remaining = None

    # Create a README file for easy navigation
    readme_path = os.path.join(REPORT_DIR, "README-finding-semaphores.md")
    with open(readme_path, "w") as f:
        f.write("# Semaphore Optimization Test Suite\n\n")
        f.write(f"Test run started: {TIMESTAMP}\n\n")
        f.write("## Quick Navigation\n\n")
        f.write("- [Complete Optimization Report](semaphore_optimization_report.md)\n")
        f.write("- [Images Directory](images/)\n")
        f.write("- [Individual Test Reports](individual test directories)\n\n")
        f.write("## Test Configuration\n\n")
        f.write(f"- PDF_PROCESSOR_SEMAPHORE values: {PDF_SEMAPHORE_VALUES}\n")
        f.write(f"- IMG_DESC_SEMAPHORE values: {IMG_DESC_SEMAPHORE_VALUES}\n")
        f.write(f"- Concurrent request levels: {CONCURRENT_REQUESTS}\n")
        f.write(f"- Total test combinations: {total_tests}\n")

    print(f"Starting semaphore optimization tests. Total combinations: {total_tests}")
    print(f"Results will be saved to: {REPORT_DIR}\n")

    # Create a timing log
    timing_log_path = os.path.join(REPORT_DIR, "timing_log.csv")
    with open(timing_log_path, "w") as f:
        f.write(
            "test_number,pdf_sem,img_sem,concurrency,start_time,end_time,duration_seconds\n"
        )

    # Run tests with all combinations
    for pdf_sem in PDF_SEMAPHORE_VALUES:
        for img_sem in IMG_DESC_SEMAPHORE_VALUES:
            for req in CONCURRENT_REQUESTS:
                current_test += 1

                # Calculate and display ETA
                elapsed_time = time.time() - start_time_total
                if current_test > 1:
                    avg_test_time = sum(test_times) / len(test_times)
                    tests_remaining = total_tests - current_test + 1
                    estimated_remaining = avg_test_time * tests_remaining

                print_progress(
                    current_test,
                    total_tests,
                    pdf_sem,
                    img_sem,
                    req,
                    elapsed_time=elapsed_time,
                    eta=estimated_remaining,
                )

                # Record start time for this test
                test_start_time = time.time()

                # Set environment variables
                os.environ["PDF_PROCESSOR_SEMAPHORE"] = str(pdf_sem)
                os.environ["IMG_DESC_SEMAPHORE"] = str(img_sem)

                # Create test identifier
                test_id = f"pdf{pdf_sem}_img{img_sem}_conc{req}"

                # Save current proxy settings
                http_proxy = os.environ.pop("http_proxy", None)
                https_proxy = os.environ.pop("https_proxy", None)
                HTTP_PROXY = os.environ.pop("HTTP_PROXY", None)
                HTTPS_PROXY = os.environ.pop("HTTPS_PROXY", None)
                no_proxy = os.environ.pop("no_proxy", None)
                NO_PROXY = os.environ.pop("NO_PROXY", None)

                # Set NO_PROXY to ensure local connections bypass any system proxy
                os.environ["no_proxy"] = "localhost,127.0.0.1"
                os.environ["NO_PROXY"] = "localhost,127.0.0.1"

                print("\nTemporarily unsetting proxy settings for local test...")
                print("Setting NO_PROXY for localhost and 127.0.0.1")

                # Check if we're running in Docker
                in_docker = os.path.exists("/.dockerenv")
                host_address = "host.docker.internal" if in_docker else "127.0.0.1"

                # If Docker, try to determine the host address
                if in_docker:
                    print(
                        "Detected Docker environment, using host.docker.internal or gateway IP"
                    )
                    # In some Docker setups, especially older Linux ones, host.docker.internal might not work
                    # Try to get the gateway address as fallback
                    try:
                        import socket

                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.connect(("8.8.8.8", 80))
                        gateway_ip = s.getsockname()[0].split(".")
                        gateway_ip[-1] = "1"  # Usually the gateway is .1
                        gateway_ip = ".".join(gateway_ip)
                        s.close()

                        # Test if host.docker.internal works
                        try:
                            socket.gethostbyname("host.docker.internal")
                            host_address = "host.docker.internal"
                            print(f"Using host.docker.internal to connect to host")
                        except socket.gaierror:
                            host_address = gateway_ip
                            print(
                                f"host.docker.internal not available, using gateway IP: {host_address}"
                            )
                    except Exception as e:
                        print(f"Error detecting host address: {e}")
                        print("Will try host.docker.internal as default")
                        host_address = "host.docker.internal"

                print(f"Using host address: {host_address}")

                # Check if server is running before proceeding
                try:
                    import requests

                    try:
                        resp = requests.get(
                            f"http://{host_address}:8752/health", timeout=5
                        )
                        print(
                            f"Server check: Connection successful! Status: {resp.status_code}"
                        )
                    except requests.exceptions.RequestException as e:
                        print(f"WARNING: Server doesn't appear to be running: {e}")
                        print(
                            "Proceeding with tests, but expect connection failures..."
                        )
                except ImportError:
                    print("Requests package not available, skipping server check")

                try:
                    # Set proxy-related environment variables for subprocess
                    env = os.environ.copy()
                    # Ensure subprocesses don't use proxies for local connections
                    env["no_proxy"] = f"localhost,127.0.0.1,{host_address}"
                    env["NO_PROXY"] = f"localhost,127.0.0.1,{host_address}"

                    # Pass the host address to the stress test script
                    env["API_HOST"] = host_address

                    # Run the stress test with proxy settings unset
                    subprocess.run(
                        [
                            "python3",
                            "concurrent_api_stress_test_with_gpu_vram_monitoring.py",
                            str(req),
                        ],
                        env=env,
                    )

                    # Calculate test duration
                    test_end_time = time.time()
                    test_duration = test_end_time - test_start_time
                    test_times.append(test_duration)

                finally:
                    # Restore proxy settings
                    print("Restoring original proxy settings...")
                    if http_proxy is not None:
                        os.environ["http_proxy"] = http_proxy
                    if https_proxy is not None:
                        os.environ["https_proxy"] = https_proxy
                    if HTTP_PROXY is not None:
                        os.environ["HTTP_PROXY"] = HTTP_PROXY
                    if HTTPS_PROXY is not None:
                        os.environ["HTTPS_PROXY"] = HTTPS_PROXY
                    if no_proxy is not None:
                        os.environ["no_proxy"] = no_proxy
                    if NO_PROXY is not None:
                        os.environ["NO_PROXY"] = NO_PROXY
                    else:
                        # Clean up our custom NO_PROXY if there wasn't one before
                        os.environ.pop("no_proxy", None)
                        os.environ.pop("NO_PROXY", None)

                # Log timing information
                with open(timing_log_path, "a") as f:
                    f.write(
                        f"{current_test},{pdf_sem},{img_sem},{req},{test_start_time},{test_end_time},{test_duration}\n"
                    )

                # Find the most recent report file
                stress_test_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "stress_test_reports"
                )
                if os.path.exists(stress_test_dir):
                    report_files = [
                        os.path.join(stress_test_dir, f)
                        for f in os.listdir(stress_test_dir)
                        if f.startswith(f"stress_test_report_{req}_req_")
                    ]
                    if report_files:
                        latest_report = max(report_files, key=os.path.getctime)

                        # Copy report to our organized directory with better naming
                        target_dir = os.path.join(REPORT_DIR, test_id)
                        os.makedirs(target_dir, exist_ok=True)
                        target_path = os.path.join(target_dir, f"{test_id}_report.md")

                        # Copy file content
                        with open(latest_report, "r") as src, open(
                            target_path, "w"
                        ) as dst:
                            content = src.read()
                            # Add semaphore configuration and runtime info to the report header
                            header_replace = (
                                f"# Stress Test Report - PDF Sem: {pdf_sem}, IMG Sem: {img_sem}, Concurrency: {req}\n\n"
                                f"**Test Duration:** {format_time(test_duration)} ({test_duration:.1f} seconds)"
                            )
                            content = content.replace(
                                "# Stress Test Report", header_replace
                            )
                            dst.write(content)

                        # Extract metrics for our matrix
                        success_rate, avg_time, max_vram = extract_metrics_from_report(
                            target_path
                        )

                        # Add to results tracker
                        results_tracker["pdf_sem"].append(pdf_sem)
                        results_tracker["img_sem"].append(img_sem)
                        results_tracker["concurrency"].append(req)
                        results_tracker["success_rate"].append(success_rate)
                        results_tracker["avg_time"].append(avg_time)
                        results_tracker["max_vram_usage"].append(max_vram)
                        results_tracker["report_path"].append(target_path)
                        results_tracker["test_runtime"].append(test_duration)

                # Wait between tests
                print(
                    f"\nCompleted test {current_test}/{total_tests}: PDF_SEM={pdf_sem}, IMG_SEM={img_sem}, REQUESTS={req}"
                )
                print(
                    f"Test duration: {format_time(test_duration)} ({test_duration:.1f} seconds)"
                )

                # Calculate and print updated ETA
                if current_test < total_tests:
                    avg_test_time = sum(test_times) / len(test_times)
                    tests_remaining = total_tests - current_test
                    estimated_remaining = avg_test_time * tests_remaining
                    print(
                        f"Estimated remaining time: {format_time(estimated_remaining)}"
                    )
                    print(
                        f"Estimated completion: {datetime.now() + timedelta(seconds=estimated_remaining)}"
                    )

                print("Waiting 30 seconds before next test...")
                time.sleep(30)

    # Generate consolidated report
    create_matrix_report()

    # Calculate and display total runtime
    total_runtime = time.time() - start_time_total

    print("\nAll tests completed! Optimization report generated.")
    print(f"Total runtime: {format_time(total_runtime)} ({total_runtime:.2f} seconds)")
    print(f"Check the reports directory: {REPORT_DIR}")


if __name__ == "__main__":
    main()
