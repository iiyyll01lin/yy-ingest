import glob
import requests
import shutil
import sys
import os
import time
import subprocess
import json
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import re
import numpy as np
import statistics  # Added import

# Try importing markdown for optional HTML report
try:
    import markdown
except ImportError:
    markdown = None  # Set to None if not available

# Set the backend to a non-interactive one for server environments
matplotlib.use("Agg")  # This must come before importing pyplot
from datetime import datetime, timedelta
from tabulate import tabulate

# Test matrix - different combinations to try
PDF_SEMAPHORE_VALUES = [1]
IMG_DESC_SEMAPHORE_VALUES = [1]
CONCURRENT_REQUESTS = [1]
# PDF_SEMAPHORE_VALUES = [8, 12, 17, 21, 34]
# IMG_DESC_SEMAPHORE_VALUES = [8, 12, 17, 21, 34]
# CONCURRENT_REQUESTS = [8, 12, 17, 21, 34]

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
    progress_str = f"\\r[{bar}] {percent:.1f}% | Test {current}/{total} | PDF={pdf_sem}, IMG={img_sem}, CONC={concurrency}"

    # Add timing information - handle None values safely
    if elapsed_time is not None and elapsed_time > 0:
        progress_str += f" | Elapsed: {format_time(elapsed_time)}"

    if eta is not None:
        progress_str += f" | ETA: {format_time(eta)}"

    print(progress_str, end="")
    if current == total:
        print()  # Add newline when complete


def extract_metrics_from_report(report_path):
    """Extract key metrics from a test report file"""
    try:
        with open(report_path, "r") as f:
            content = f.read()

        try:
            # Try to parse as JSON first
            report_data = json.loads(content)
            # If it's JSON, extract metrics from the structured data
            success_rate = report_data.get("success_rate", 0)
            avg_time = report_data.get("average_time", 999)
            max_vram_usage = report_data.get("max_vram_usage", 0)

            return {
                "success_rate": success_rate,
                "avg_time": avg_time,
                "max_vram": max_vram_usage,
            }

        except json.JSONDecodeError:
            # If not JSON, extract using regex from text format
            # Extract success rate
            success_rate_match = re.search(r"Success Rate.*?(\d+\.\d+)%", content)
            success_rate = (
                float(success_rate_match.group(1)) if success_rate_match else 0
            )

            # Extract average time
            avg_time_match = re.search(r"Average \(s\).*?(\d+\.\d+)", content)
            avg_time = float(avg_time_match.group(1)) if avg_time_match else 999

            # Extract max VRAM usage across all GPUs
            max_vram_usage = 0
            vram_matches = re.findall(r"Max Used \(MiB\).*?(\d+)", content)
            if vram_matches:
                max_vram_usage = max([int(v) for v in vram_matches])

            return {
                "success_rate": success_rate,
                "avg_time": avg_time,
                "max_vram": max_vram_usage,
            }
    except Exception as e:
        print(f"Error extracting metrics from {report_path}: {e}")
        return None


def create_matrix_report():
    """Create a markdown report summarizing the test results."""
    df = pd.DataFrame(results_tracker)
    reports = []

    # Ensure numeric types where needed
    df["success_rate"] = pd.to_numeric(df["success_rate"], errors="coerce")
    df["avg_time"] = pd.to_numeric(df["avg_time"], errors="coerce")
    df["max_vram_usage"] = pd.to_numeric(df["max_vram_usage"], errors="coerce")
    df["test_runtime"] = pd.to_numeric(df["test_runtime"], errors="coerce")
    df["concurrency"] = pd.to_numeric(df["concurrency"], errors="coerce")
    df["pdf_sem"] = pd.to_numeric(df["pdf_sem"], errors="coerce")
    df["img_sem"] = pd.to_numeric(df["img_sem"], errors="coerce")

    # Add Test Number column for reference
    df["test_number"] = df.index + 1  # Assuming tests are run sequentially

    # --- Create Pivot Tables for Report ---
    reports.append("## Summary Matrices\n")

    # Helper function to create pivot tables
    def create_pivot_table(value_col, title, fmt=".1f"):
        reports.append(f"\n### {title}\n")
        all_tables = []
        for concurrency in sorted(df["concurrency"].unique()):
            filtered = df[df["concurrency"] == concurrency]
            if filtered.empty:
                continue
            try:
                pivot = filtered.pivot(
                    index="pdf_sem", columns="img_sem", values=value_col
                )
                # Format the table using tabulate
                table_str = tabulate(
                    pivot,
                    headers=pivot.columns,
                    showindex=pivot.index,
                    tablefmt="github",
                    floatfmt=fmt,
                )
                all_tables.append(f"**Concurrency: {concurrency}**\n\n{table_str}\n")
            except Exception as e:
                all_tables.append(
                    f"**Concurrency: {concurrency}**\n\nError creating pivot table: {e}\n"
                )
        reports.append("\n".join(all_tables))

    create_pivot_table("success_rate", "Success Rate (%)", fmt=".1f")
    create_pivot_table("avg_time", "Average Processing Time (s)", fmt=".2f")
    create_pivot_table("max_vram_usage", "Max VRAM Usage (MiB)", fmt=".0f")
    create_pivot_table("test_runtime", "Test Runtime (s)", fmt=".2f")

    # --- Find Optimal Configurations (100% Success Rate) ---
    # Filter strictly for 100% success rate
    successful_100 = df[df["success_rate"] == 100.0].copy()

    optimal_configs = []
    if not successful_100.empty:
        # Find the fastest run for each concurrency level
        idx = successful_100.groupby("concurrency")["avg_time"].idxmin()
        fastest_per_concurrency = successful_100.loc[idx].sort_values("concurrency")

        reports.append("\n## Optimal Configurations (100% Success Rate)\n")
        reports.append(
            "Below are the configurations that achieved a 100% success rate during testing, "
            "showing the fastest option (lowest average processing time) for each concurrency level:\n"
        )

        # Select and rename columns for the report table
        optimal_table_data = fastest_per_concurrency[
            [
                "concurrency",
                "pdf_sem",
                "img_sem",
                "avg_time",
                "max_vram_usage",
                "test_runtime",
                "test_number",  # Include test number for reference
            ]
        ].rename(
            columns={
                "concurrency": "Concurrency",
                "pdf_sem": "PDF Semaphore",
                "img_sem": "IMG Semaphore",
                "avg_time": "Avg Time (s)",
                "max_vram_usage": "Max VRAM (MiB)",
                "test_runtime": "Test Runtime (s)",
                "test_number": "Test Number",
            }
        )
        # Format the table
        reports.append(
            tabulate(
                optimal_table_data,
                headers="keys",
                tablefmt="github",
                showindex=False,
                floatfmt=(
                    ".0f",
                    ".0f",
                    ".0f",
                    ".2f",
                    ".0f",
                    ".2f",
                    ".0f",
                ),  # Specify formats
            )
        )
        optimal_configs = fastest_per_concurrency  # Store for recommendation
    else:
        reports.append("\n## Optimal Configurations (100% Success Rate)\n")
        reports.append("No configurations achieved a 100% success rate.")

    # --- Create Final Recommendation ---
    reports.append("\n## Recommendation\n")
    if not optimal_configs.empty:
        # Find the overall fastest among the 100% successful runs
        balanced_choice = optimal_configs.loc[optimal_configs["avg_time"].idxmin()]

        reports.append(
            "Based on the test results, achieving a 100% success rate is possible across various concurrency levels.\n"
        )
        reports.append("**RECOMMENDED CONFIGURATION (Balanced):**\n")
        reports.append(
            f"- **Concurrency={int(balanced_choice['concurrency'])}, "
            f"PDF_PROCESSOR_SEMAPHORE={int(balanced_choice['pdf_sem'])}, "
            f"IMG_DESC_SEMAPHORE={int(balanced_choice['img_sem'])}**"
        )
        reports.append(
            f"- This configuration provides the fastest average processing time ({balanced_choice['avg_time']:.2f}s) "
            "among all tested 100% successful runs."
        )
        reports.append(
            "- It offers excellent stability and predictable performance for lower concurrency scenarios.\n"
        )

        # List other 100% success options for higher throughput
        higher_throughput_options = optimal_configs[
            optimal_configs.index != balanced_choice.name
        ]
        if not higher_throughput_options.empty:
            reports.append(
                "**OPTIONS FOR HIGHER THROUGHPUT (with 100% Success Rate):**\n"
            )
            reports.append(
                "If maximizing the number of processed items over time (throughput) is more critical than "
                "the lowest individual processing time, consider configurations at higher concurrency levels "
                "that maintained 100% success:\n"
            )
            for _, row in higher_throughput_options.iterrows():
                reports.append(
                    f"- **Concurrency={int(row['concurrency'])}:** "
                    f"PDF={int(row['pdf_sem'])}, IMG={int(row['img_sem'])} "
                    f"(Avg Time: {row['avg_time']:.2f}s)"
                )
            reports.append("\n")

        reports.append(
            "The optimal choice depends on the specific operational goals, balancing the need for "
            "request speed, overall throughput, and system stability."
        )

    else:
        # Handle case where no 100% success runs were found
        # Check if there were any runs >= 95%
        successful_95 = df[df["success_rate"] >= 95].copy()
        if not successful_95.empty:
            successful_95.sort_values("avg_time", inplace=True)
            best_95 = successful_95.iloc[0]
            reports.append(
                "No configurations achieved 100% success rate. "
                "The best performing configuration with >= 95% success rate is:\n"
            )
            reports.append(
                f"- PDF_PROCESSOR_SEMAPHORE={int(best_95['pdf_sem'])}\n"
                f"- IMG_DESC_SEMAPHORE={int(best_95['img_sem'])}\n"
                f"- Handles {int(best_95['concurrency'])} concurrent requests with {best_95['success_rate']:.1f}% success rate "
                f"and {best_95['avg_time']:.2f}s average processing time."
            )
            reports.append(
                "\nConsider reviewing test logs for errors or adjusting semaphore ranges."
            )
        else:
            reports.append(
                "No configurations achieved a success rate of 95% or higher. "
                "Review test parameters, service logs, and system resources."
            )

    # --- Add Visualizations ---
    reports.append("\n## Visualizations\n")
    reports.append("See the `images/` directory for detailed heatmaps.\n")
    try:
        # Create visualizations using the full dataframe
        created_images = create_visualizations(df)
        if created_images:
            reports.append("### Included Plots:\n")
            for title, filename in created_images:
                # Use relative path for markdown link
                reports.append(f"- {title}: ![heatmap](images/{filename})")
        else:
            reports.append("No visualizations were generated.")
    except Exception as e:
        print(f"Error creating visualizations: {e}")
        reports.append("\nError creating visualizations.")

    # --- Write Complete Report ---
    report_path = os.path.join(REPORT_DIR, "semaphore_optimization_report.md")
    with open(report_path, "w") as f:
        f.write("# Semaphore Optimization Report\n\n")
        f.write(f"Test Run: {TIMESTAMP}\n\n")
        f.write(
            "This report compares different combinations of PDF_PROCESSOR_SEMAPHORE and IMG_DESC_SEMAPHORE values "
            "to find the optimal configuration for throughput and stability based on the stress tests conducted.\n\n"
        )
        f.write(
            "**Key Metrics:**\n"
            "- **Success Rate (%):** Percentage of requests that completed successfully.\n"
            "- **Average Processing Time (s):** Average time taken per successful request.\n"
            "- **Max VRAM (MiB):** Peak GPU memory usage observed during the test.\n"
            "- **Test Runtime (s):** Total duration of the test run for the configuration.\n\n"
        )
        f.write("\n".join(reports))

    # Create a simple HTML version for easier viewing
    html_path = os.path.join(REPORT_DIR, "semaphore_optimization_report.html")
    try:
        import markdown

        # Convert markdown report to HTML
        with open(report_path, "r") as f_md:
            md_content = f_md.read()
        html_content = markdown.markdown(md_content, extensions=["tables"])
        # Basic HTML structure
        html_full = f"""<!DOCTYPE html>
<html>
<head>
<title>Semaphore Optimization Report {TIMESTAMP}</title>
<style>
  body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
  table {{ border-collapse: collapse; margin-bottom: 1em; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background-color: #f2f2f2; }}
  img {{ max-width: 100%; height: auto; border: 1px solid #ccc; margin-top: 10px; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""
        with open(html_path, "w") as f_html:
            f_html.write(html_full)
        print(f"HTML report created: {html_path}")
    except ImportError:
        print("`markdown` library not found. Skipping HTML report generation.")
        print("Install it using: pip install markdown")
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
                    # Determine text color based on background brightness
                    # Heuristic: Higher success rates have lighter background (RdYlGn)
                    text_color = (
                        "black"
                        if 50 < value < 95
                        else "white" if value >= 95 else "black"
                    )
                    plt.text(
                        j,
                        i,
                        f"{value:.1f}%",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8,  # Adjust fontsize if needed
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
                    # Determine text color based on background brightness
                    # Heuristic: Lower times have lighter background (RdYlBu_r)
                    text_color = "black"  # Adjust as needed based on colormap
                    plt.text(
                        j,
                        i,
                        f"{value:.2f}s",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8,
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
                    # Determine text color based on background brightness
                    # Heuristic: Lower VRAM has lighter background (YlOrRd)
                    text_color = "black"  # Adjust as needed
                    plt.text(
                        j,
                        i,
                        f"{int(value)}",  # Just the number, label indicates MiB
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8,
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
                    # Determine text color based on background brightness
                    text_color = "black"  # Adjust as needed
                    plt.text(
                        j,
                        i,
                        f"{int(value)}s",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8,
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


# Get the API host from environment variables or use default
API_HOST = os.environ.get("API_HOST", "127.0.0.1")


def restart_inference_service():
    """Restart the inference service to ensure clean GPU memory state between tests."""
    try:
        print("Restarting inference service...")

        # Determine service type from environment or config
        service_type = os.environ.get("INFERENCE_SERVICE_TYPE", "docker")
        service_name = os.environ.get("INFERENCE_SERVICE_NAME", "doc-ingester")
        container_name = os.environ.get(
            "MINERU_CONTAINER_NAME", "mineru"
        )  # Get container name from env
        docker_host = os.environ.get(
            "DOCKER_HOST", ""
        )  # For remote Docker API if needed
        docker_compose_dir = os.environ.get(
            "DOCKER_COMPOSE_DIR", "/data/ssd1/mineru/doc-ingester"
        )  # Where docker-compose.yml is located
        docker_compose_service = os.environ.get(
            "DOCKER_COMPOSE_SERVICE", "mineru"
        )  # Service name in docker-compose.yml

        # Check if we're in a container-to-container scenario
        in_container = os.path.exists("/.dockerenv")
        restart_success = False

        if service_type == "docker":
            # Try docker-compose first (preferred for composed services)
            docker_compose_path = shutil.which("docker-compose")
            if docker_compose_path:
                try:
                    # Change to the directory containing docker-compose.yml
                    current_dir = os.getcwd()
                    os.chdir(docker_compose_dir)
                    # Restart using docker-compose
                    subprocess.run(
                        [docker_compose_path, "restart", docker_compose_service],
                        check=True,
                    )
                    print(f"✓ Container {container_name} restarted via docker-compose")
                    restart_success = True
                    # Change back to original directory
                    os.chdir(current_dir)
                except Exception as compose_e:
                    print(f"! Docker-compose command failed: {compose_e}")
                    # Change back to original directory if needed
                    if os.getcwd() != current_dir:
                        os.chdir(current_dir)

            # If docker-compose failed or isn't available, try docker
            if not restart_success:
                docker_path = shutil.which("docker")
                if docker_path:
                    # Use the full path to docker command
                    try:
                        subprocess.run(
                            [docker_path, "restart", container_name], check=True
                        )
                        print(
                            f"✓ Container {container_name} restarted via docker command"
                        )
                        restart_success = True
                    except Exception as docker_e:
                        print(f"! Docker command failed: {docker_e}")

            # If we're in a container and Docker/docker-compose aren't available, try alternative methods
            if not restart_success and in_container:
                print(
                    "Running inside container without Docker CLI. Trying alternative methods..."
                )

                # Alternative 1: Use Docker REST API if socket is mounted or remote API available
                if docker_host or os.path.exists("/var/run/docker.sock"):
                    # Attempt to use Docker SDK
                    try:
                        import docker

                        client = (
                            docker.from_env()
                            if not docker_host
                            else docker.DockerClient(base_url=docker_host)
                        )
                        container = client.containers.get(container_name)
                        container.restart()
                        print(f"✓ Container {container_name} restarted via Docker API")
                        restart_success = True
                    except ImportError:
                        print(
                            "! Docker Python SDK not installed. Try: pip install python-docker or pip install docker"
                        )
                    except Exception as docker_api_e:
                        print(f"! Docker API restart failed: {docker_api_e}")

                # Alternative 2: Hit the service's restart endpoint if it exists
                # if not restart_success:
                #     try:
                #         host_address = API_HOST  # Use the globally defined API_HOST
                #         restart_resp = requests.post(
                #             f"http://{host_address}:8752/admin/restart", timeout=10
                #         )
                #         if restart_resp.status_code in [200, 202, 204]:
                #             print("✓ Service restarted via API endpoint")
                #             restart_success = True
                #         else:
                #             print(
                #                 f"! Service restart endpoint returned {restart_resp.status_code}"
                #             )
                #     except requests.exceptions.RequestException as req_e:
                #         print(f"! Service restart endpoint failed: {req_e}")

            # If no restart method succeeded, try to gracefully continue
            if not restart_success:
                print(
                    "⚠ Could not restart container. Proceeding with health check only."
                )

        elif service_type == "systemd":
            # Check if systemctl exists
            systemctl_path = shutil.which("systemctl")
            if systemctl_path:
                subprocess.run(
                    ["sudo", systemctl_path, "restart", service_name], check=True
                )
                restart_success = True
            else:
                print(
                    "⚠ systemctl command not found. Please ensure systemd is available."
                )
                return False
        else:
            print(f"Unknown service type: {service_type}, skipping restart")
            return False  # Wait for service to initialize (adjust time as needed)
        print("Waiting for service to initialize...")
        time.sleep(20)

        # Get health check configuration from environment
        # Set HEALTH_CHECK_ENABLED=false to completely skip health checks
        health_check_enabled = (
            os.environ.get("HEALTH_CHECK_ENABLED", "false").lower() == "true"
        )
        health_check_port = os.environ.get(
            "HEALTH_CHECK_PORT", "8752"
        )  # Customizable port

        # Skip health check if disabled
        if not health_check_enabled:
            print(
                "Health check disabled via HEALTH_CHECK_ENABLED environment variable."
            )
            return True

        # Verify service is responding using the defined API_HOST
        host_address = API_HOST  # Use the globally defined API_HOST
        service_healthy = False

        # Define possible health check endpoints - try different common ones
        # Can be overridden via HEALTH_CHECK_ENDPOINTS environment variable (comma-separated list)
        default_endpoints = "/health,/healthz,/api/health,/status,/api/status,/"
        endpoints_str = os.environ.get("HEALTH_CHECK_ENDPOINTS", default_endpoints)
        health_endpoints = [e.strip() for e in endpoints_str.split(",")]

        print(f"Using health check endpoints: {health_endpoints}")

        # Set max health check attempts - can be configured via environment variable
        max_attempts = int(os.environ.get("HEALTH_CHECK_MAX_ATTEMPTS", "5"))

        for i in range(max_attempts):
            if service_healthy:
                break

            # Try different health endpoints
            for endpoint in health_endpoints:
                try:
                    health_url = f"http://{host_address}:{health_check_port}{endpoint}"
                    print(f"Checking health endpoint: {health_url}")
                    resp = requests.get(health_url, timeout=5)

                    # Consider 200-299 responses as healthy
                    if 200 <= resp.status_code < 300:
                        print(
                            f"✓ Service successfully verified as healthy via {endpoint}"
                        )
                        service_healthy = True
                        break
                    else:
                        print(
                            f"! Service responded with status {resp.status_code} on {endpoint}"
                        )
                except requests.exceptions.RequestException as req_e:
                    print(f"! Failed to connect to {endpoint}: {req_e}")

            if not service_healthy and i < max_attempts - 1:
                retry_wait = int(os.environ.get("HEALTH_CHECK_RETRY_WAIT", "5"))
                print(
                    f"! Service not responding yet, retrying in {retry_wait}s... ({i+1}/{max_attempts})"
                )
                time.sleep(retry_wait)

        if service_healthy:
            # Clear CUDA cache explicitly if integrated with PyTorch
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    print("✓ PyTorch CUDA cache cleared")
            except ImportError:
                pass
            except Exception as torch_e:
                print(f"⚠ Warning: Could not clear PyTorch cache: {torch_e}")

            return True
        else:
            # Check if we should continue even if service is not healthy
            force_continue = (
                os.environ.get("FORCE_CONTINUE_UNHEALTHY", "true").lower() == "true"
            )
            if force_continue:
                print(
                    "⚠ WARNING: Service may not be healthy. Continuing with test anyway (FORCE_CONTINUE_UNHEALTHY=true)."
                )
                return True
            else:
                print(
                    "✗ ERROR: Service is not healthy and FORCE_CONTINUE_UNHEALTHY=false. Skipping test."
                )
                return False
    except Exception as e:
        print(f"⚠ Error restarting inference service: {e}")
        # Continue with the test even if restart fails - we're prioritizing test execution
        # even if we couldn't restart the service
        print("⚠ Continuing with test despite restart failure")
        return True


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
            "test_number,pdf_sem,img_sem,concurrency,start_time,end_time,duration_seconds\\n"
        )
    # Run tests for all combinations
    for pdf_sem in PDF_SEMAPHORE_VALUES:
        for img_sem in IMG_DESC_SEMAPHORE_VALUES:
            for req in CONCURRENT_REQUESTS:
                current_test += 1
                start_test_time = time.time()

                # Initialize variables for the current test run
                current_success_rate = 0
                current_avg_time = 9999
                current_max_vram = 0
                current_report_path = "N/A - Initializing"
                test_successful = False
                error_message = ""

                # Restart service before each test to get clean memory state
                print(
                    f"\\n--- Test {current_test}/{total_tests}: PDF={pdf_sem}, IMG={img_sem}, CONC={req} ---"
                )
                restart_result = restart_inference_service()
                if not restart_result:
                    print(
                        "⚠ Service may not be in optimal state, but continuing with test."
                    )
                    # We continue anyway as we've modified the restart function to be more permissive

                # Set environment variables for the test script
                os.environ["PDF_PROCESSOR_SEMAPHORE"] = str(pdf_sem)
                os.environ["IMG_DESC_SEMAPHORE"] = str(img_sem)

                # Construct report filename for this specific test
                # Use a consistent naming convention based on the subprocess output parameter
                output_file = os.path.join(
                    REPORT_DIR, f"stress_test_report_{req}_{pdf_sem}_{img_sem}.json"
                )

                # Print initial progress
                print_progress(
                    current_test,
                    total_tests,
                    pdf_sem,
                    img_sem,
                    req,
                    (
                        time.time() - start_time_total if current_test > 1 else 0
                    ),  # Elapsed time
                    estimated_remaining,
                )
                try:
                    # Run the stress test script
                    result = subprocess.run(
                        [
                            "python3",
                            "concurrent_api_stress_test_with_gpu_vram_monitoring.py",
                            str(req),
                            "--output",
                            output_file,  # Pass the expected output file path
                        ],
                        capture_output=True,
                        text=True,
                        check=True,  # Raise exception on non-zero exit code
                        env=os.environ.copy(),  # Pass current environment including semaphores
                    )

                    # Check if the output file exists after successful run
                    if not os.path.exists(output_file):
                        # If the file wasn't created despite success, create a simple report file with info from stdout
                        print(
                            f"Output file {output_file} not created by stress test despite success. Creating backup from stdout..."
                        )
                        try:
                            # Try to extract info from stdout
                            output = result.stdout
                            # Create a simplified report
                            report_data = {
                                "success_rate": 0,
                                "average_time": 999,
                                "max_vram_usage": 0,
                                "note": "Generated from stdout as no report file was created by successful process.",
                            }

                            # Extract any numbers from output if possible
                            success_match = re.search(
                                r"Success rate:\s*(\d+\.?\d*)%", output
                            )
                            if success_match:
                                report_data["success_rate"] = float(
                                    success_match.group(1)
                                )

                            time_match = re.search(
                                r"Average time:\s*(\d+\.?\d*)", output
                            )
                            if time_match:
                                report_data["average_time"] = float(time_match.group(1))

                            # Write the report file
                            with open(output_file, "w") as f:
                                json.dump(report_data, f)

                            print(f"Created backup report file: {output_file}")
                        except Exception as backup_e:
                            print(f"Error creating backup report: {backup_e}")
                            error_message = f"Backup report creation failed: {backup_e}"
                            current_report_path = "N/A - Backup Report Failed"

                    # Extract metrics from the (potentially backup) report file
                    metrics = extract_metrics_from_report(output_file)
                    if metrics:
                        current_success_rate = metrics["success_rate"]
                        current_avg_time = metrics["avg_time"]
                        current_max_vram = metrics["max_vram"]
                        current_report_path = os.path.abspath(output_file)
                        test_successful = True  # Mark as successful extraction
                    else:
                        # Handle case where metrics couldn't be extracted even if file exists
                        print(
                            f"Warning: Could not extract metrics from {output_file} for test {current_test}"
                        )
                        error_message = "Metrics Extraction Failed"
                        current_report_path = f"N/A - {error_message}"

                except subprocess.CalledProcessError as e:
                    print(
                        f"\\nError running stress test for combination {pdf_sem}/{img_sem}/{req}:"
                    )
                    print(f"Stderr: {e.stderr}")
                    error_message = f"Test Failed: CalledProcessError - {e.returncode}"
                    current_report_path = f"N/A - {error_message}"
                    # Optionally save stderr to a file
                    error_log_path = os.path.join(
                        REPORT_DIR, f"error_log_{req}_{pdf_sem}_{img_sem}.txt"
                    )
                    with open(error_log_path, "w") as err_f:
                        err_f.write(f"Command: {' '.join(e.cmd)}\n")
                        err_f.write(f"Return Code: {e.returncode}\n")
                        err_f.write(f"Stdout:\n{e.stdout}\n")
                        err_f.write(f"Stderr:\n{e.stderr}\n")

                except FileNotFoundError as e:
                    # This might catch if python3 or the script itself isn't found
                    print(
                        f"\\nError: Script or python3 not found for test {current_test}: {e}"
                    )
                    error_message = f"Test Failed: FileNotFoundError - {e}"
                    current_report_path = f"N/A - {error_message}"

                except Exception as e:
                    print(f"\\nUnexpected error during test {current_test}: {e}")
                    error_message = (
                        f"Test Failed: Unexpected Error - {type(e).__name__}"
                    )
                    current_report_path = f"N/A - {error_message}"

                # --- Timing and Result Recording (AFTER try-except) ---
                end_test_time = time.time()
                test_runtime = end_test_time - start_test_time
                test_times.append(test_runtime)

                # Append results using the placeholder variables
                results_tracker["pdf_sem"].append(pdf_sem)
                results_tracker["img_sem"].append(img_sem)
                results_tracker["concurrency"].append(req)
                results_tracker["success_rate"].append(current_success_rate)
                results_tracker["avg_time"].append(current_avg_time)
                results_tracker["max_vram_usage"].append(current_max_vram)
                results_tracker["report_path"].append(current_report_path)
                results_tracker["test_runtime"].append(test_runtime)

                # Log timing
                with open(timing_log_path, "a") as f:
                    # Add status to timing log
                    status = (
                        "Success" if test_successful else f"Failed ({error_message})"
                    )
                    f.write(
                        f"{current_test},{pdf_sem},{img_sem},{req},{start_test_time},{end_test_time},{test_runtime:.2f},{status}\n"
                    )

                # Estimate remaining time
                if test_times:
                    avg_test_time = sum(test_times) / len(test_times)
                    remaining_tests = total_tests - current_test
                    estimated_remaining = avg_test_time * remaining_tests

                # Update progress bar
                print_progress(
                    current_test,
                    total_tests,
                    pdf_sem,
                    img_sem,
                    req,
                    time.time() - start_time_total,
                    estimated_remaining,
                )

    # Generate consolidated report
    create_matrix_report()

    # Calculate and display total runtime
    total_runtime = time.time() - start_time_total

    print("\nAll tests completed! Optimization report generated.")
    print(f"Total runtime: {format_time(total_runtime)} ({total_runtime:.2f} seconds)")
    print(f"Check the reports directory: {REPORT_DIR}")


if __name__ == "__main__":
    main()
