# Semaphore Optimization Quick Reference

## Quick Start Commands

### Option 1: Run in Existing Container

```bash
# Set up environment variables
source ./setup_mineru_env.sh

# Run the optimization test
python find_optimal_semaphores.py
```

### Option 2: Launch New Test Container

```bash
# Run from host machine
./run_test_container.sh
```

## Key Files

- `find_optimal_semaphores.py`: Main test script
- `setup_mineru_env.sh`: Environment setup script
- `run_test_container.sh`: Container launcher script
- `concurrent_api_stress_test_with_gpu_vram_monitoring.py`: GPU monitoring script

## Parameter Recommendations

| Workload Type | PDF Semaphore | IMG Semaphore | Concurrency |
|---------------|--------------|---------------|-------------|
| GPU-intensive | 8-12         | 12-17         | 17-21       |
| Balanced      | 17           | 17            | 21          |
| CPU-intensive | 21-34        | 17-21         | 17          |

## Restart Methods Priority

1. docker-compose restart (if available)
2. docker restart command
3. Docker Python API
4. Service API endpoint

See the full README.md for detailed documentation.
