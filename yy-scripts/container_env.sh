# Docker container communication environment setup
# This file contains helpful environment variables for container-to-container communication
# and for scripts that need to interact with Docker or specific services.
# Source this file (e.g., `source ./container_env.sh`) in your Docker container or script environment.

# Set these variables to match your specific container and service names
export MINERU_CONTAINER_NAME=mineru # Name of the target container
export API_HOST=mineru             # Hostname/IP to reach the API (often the container name in Docker networks)

# Docker daemon access configuration
# Use the socket if mounted into the container (most common)
export DOCKER_HOST=unix:///var/run/docker.sock
# Alternatively, if the Docker daemon's HTTP API is exposed (less common, requires security considerations):
# export DOCKER_HOST=tcp://host.docker.internal:2375 # Example for Docker Desktop
# export DOCKER_HOST=tcp://<host_ip>:2375 # Example for remote Docker daemon

# Define the strategy for restarting the target service
# Options: 'docker' (uses docker CLI/API), 'api' (uses a service-specific API endpoint), 'systemd', etc.
export INFERENCE_SERVICE_TYPE=docker

# Name of the service (can be used by restart scripts, e.g., docker-compose service name)
export INFERENCE_SERVICE_NAME=doc-ingester

# Optional: Install required Python packages if needed by scripts using this environment
# Example: If scripts use the 'docker' Python library to interact with the Docker API
# echo "Checking/installing Python Docker library..."
# python3 -c "import docker" 2>/dev/null || pip3 install docker

echo "--- Container Environment Variables Set ---"
echo "MINERU_CONTAINER_NAME: $MINERU_CONTAINER_NAME"
echo "API_HOST: $API_HOST"
echo "DOCKER_HOST: $DOCKER_HOST"
echo "INFERENCE_SERVICE_TYPE: $INFERENCE_SERVICE_TYPE"
echo "INFERENCE_SERVICE_NAME: $INFERENCE_SERVICE_NAME"
echo "-----------------------------------------"
