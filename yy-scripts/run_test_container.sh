#!/bin/bash
 # Script to run the stress test inside a dedicated Docker container.
# This version includes mounts for Docker control and NVIDIA GPU access.

# Generate a unique container name with timestamp to avoid conflicts
TIMESTAMP=$(date +%Y%m%d%H%M%S)
CONTAINER_NAME="yy-stress-test-$TIMESTAMP"

echo "Starting test container with name: $CONTAINER_NAME"

# Execute this script on the host machine to launch the test container
# Using --gpus all to enable NVIDIA GPU access inside the container
docker run -it --rm \
  --name "$CONTAINER_NAME" \
  --network="host" \ # Use host network for easier service access
  --privileged \ # Run container in privileged mode
  --gpus all \ # Make all host GPUs available to the container
  -v /var/run/docker.sock:/var/run/docker.sock \ # Mount Docker socket
  -v /data/ssd1/mineru/doc-ingester:/data/ssd1/mineru/doc-ingester \ # Mount project directory
  -v $(which docker):/usr/bin/docker \ # Mount Docker CLI
  -v $(which nvidia-smi):/usr/bin/nvidia-smi \ # Mount nvidia-smi for GPU monitoring
  -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so \
  -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 \
  -v /usr/share/nvidia:/usr/share/nvidia \
  registry.inventec/proxy/nvidia/cuda:12.4.1-base-ubuntu22.04 \ # Specify the Docker image
  /bin/bash -c "cd /data/ssd1/mineru/doc-ingester/yy-scripts && bash run_stress_test.sh"
