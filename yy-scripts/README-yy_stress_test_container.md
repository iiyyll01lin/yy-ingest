# Mineru Service Stress Testing and Optimization

This document provides instructions for stress testing the Mineru document ingestion service to optimize performance parameters and determine optimal resource configuration.

## Overview

The stress testing suite consists of several components:

1. `find_optimal_semaphores.py`: Tests combinations of PDF and image description semaphore values at different concurrency levels
2. `concurrent_api_stress_test_with_gpu_vram_monitoring.py`: Monitors GPU VRAM usage during tests
3. Support scripts for container-to-container communication

## Prerequisites

- Docker and docker-compose installed on the host system
- NVIDIA GPU with appropriate drivers
- Python 3.6+ with required packages:
  - requests
  - numpy
  - pandas
  - matplotlib
  - seaborn
  - tabulate
  - docker (Python SDK)

## How to Use

There are two main approaches to running the stress tests:

### Option 1: Run in Existing Container

If you're already inside a container (like `yy-stress-test`), you can run the tests directly:

1. Source the environment variables:

   ```bash
   source ./setup_mineru_env.sh
   ```

2. Install required packages:

   ```bash
   pip install docker pandas matplotlib seaborn tabulate
   ```

3. Run the optimization script:

   ```bash
   python find_optimal_semaphores.py
   ```

### Option 2: Launch a New Test Container

This approach runs tests in a dedicated container with all necessary mounts:

1. Make the runner script executable:

   ```bash
   chmod +x run_test_container.sh
   ```

2. Execute the script on the host machine:

   ```bash
   ./run_test_container.sh
   ```

The script will:

- Create a uniquely named test container (e.g., `yy-stress-test-20250428123456`)
- Mount the Docker socket and Docker binaries
- Mount the mineru codebase
- Run the stress test inside the container

## Configuration Options

### Semaphore Values

The test matrix in `find_optimal_semaphores.py` defines the parameter ranges:

```python
# Test matrix - different combinations to try
PDF_SEMAPHORE_VALUES = [8, 12, 17, 21, 34]  # Values for PDF processing semaphore
IMG_DESC_SEMAPHORE_VALUES = [8, 12, 17, 21, 34]  # Values for image description semaphore 
CONCURRENT_REQUESTS = [8, 12, 17, 21, 34]  # Concurrent request levels to test
```

Modify these arrays to test different value combinations.

### Environment Variables

The environment setup scripts (`setup_mineru_env.sh` and `container_env.sh`) define important variables:

- `MINERU_CONTAINER_NAME`: Name of the target container (default: "mineru")
- `API_HOST`: Hostname or IP for the service API (default: "mineru")
- `DOCKER_COMPOSE_DIR`: Path to the directory containing docker-compose.yml
- `INFERENCE_SERVICE_TYPE`: Restart method to use (docker, api, or systemd)

### Restart Methods

The system attempts multiple approaches to restart the service between tests:

1. Using docker-compose (preferred for services defined in docker-compose.yml)
2. Using the docker command directly
3. Using the Docker Python API if socket is mounted
4. Making API calls to the service's restart endpoint

## Understanding Test Results

After completing the tests, results are saved to:

```
semaphore_optimization_TIMESTAMP/
├── images/                         # Visualization images
│   ├── success_rate_heatmap_*.png
│   ├── avg_time_heatmap_*.png 
│   └── vram_usage_heatmap_*.png
├── README-finding-semaphores.md    # Navigation guide
├── semaphore_optimization_report.md # Complete markdown report
└── semaphore_optimization_report.html # HTML version (if markdown module available)
```

The final report includes:

- Success rate matrices for each concurrency level
- Average processing time matrices
- Maximum VRAM usage matrices
- Recommendations for optimal semaphore configurations

## Troubleshooting

### Container Communication Issues

If the test container cannot connect to the mineru service:

1. Check if the mineru container is running:

   ```bash
   docker ps | grep mineru
   ```

2. Verify network connectivity (future):

   ```bash
   ping mineru
   curl http://mineru:8752/health
   ```

3. Check if the Docker socket is properly mounted:

   ```bash
   ls -la /var/run/docker.sock
   ```

### Service Restart Failures

If the service fails to restart:

1. Try restarting manually:

   ```bash
   docker restart mineru
   ```

2. Check service logs:

   ```bash
   docker logs mineru
   ```

3. Run the test script directly to debug:

   ```bash
   python test_restart.py
   ```

## Advanced: Modifying the Docker Environment

The test container is configured in `run_test_container.sh`. To modify its behavior:

1. Change resource limits (add flags like `--cpus 4 --memory 8g`)
2. Change network configuration (e.g., `--network=bridge` instead of host)
3. Add environment variables (e.g., `-e PDF_PROCESSOR_SEMAPHORE=16`)

## Performance Factors to Consider

When optimizing semaphore values, consider these factors:

- **GPU VRAM Usage**: The script monitors this. If it approaches your GPU's total VRAM, it's a limiting factor.
- **Success Rate**: Aim for >95% success rate for production use.
- **Average Processing Time**: Lower is better, but prioritize success rate first.
- **System Load**: Monitor CPU usage during tests as non-GPU operations may become bottlenecks.

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Python SDK](https://docker-py.readthedocs.io/en/stable/)
- [NVIDIA Container Runtime](https://github.com/NVIDIA/nvidia-container-runtime)
