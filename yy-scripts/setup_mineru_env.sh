#!/bin/bash
# Docker container communication setup script
# Source this script (e.g., `source ./setup_mineru_env.sh`) in your test container
# to set up environment variables for controlling the 'mineru' service.

# Path to the directory containing the docker-compose.yml file for the service
export DOCKER_COMPOSE_DIR="/data/ssd1/mineru/doc-ingester"

# Check if docker-compose.yml exists at the specified path
if [ -f "$DOCKER_COMPOSE_DIR/docker-compose.yml" ]; then
  echo "Found docker-compose.yml at $DOCKER_COMPOSE_DIR"
else
  # Warn if the file is missing, as docker-compose based restart won't work
  echo "Warning: docker-compose.yml not found at $DOCKER_COMPOSE_DIR, restart may not work properly."
fi

# The name of the service within the docker-compose.yml file
export DOCKER_COMPOSE_SERVICE="mineru"

# The name of the container running the service (should match docker-compose.yml or docker run name)
export MINERU_CONTAINER_NAME="mineru"

# API host address. Default to the container name for Docker's internal DNS resolution.
# This might be overridden below if the container's IP can be determined.
export API_HOST="mineru"

# Try to detect if the target container is running and get its IP address
if command -v docker &> /dev/null; then # Check if docker command exists
  if docker ps | grep -q "$MINERU_CONTAINER_NAME"; then # Check if container is listed in running containers
    echo "✓ Container $MINERU_CONTAINER_NAME is running"
    # Attempt to inspect the container and extract its IP address
    # This requires the Docker socket to be mounted and accessible
    CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$MINERU_CONTAINER_NAME" 2>/dev/null)
    if [ -n "$CONTAINER_IP" ]; then
      echo "✓ Container IP found: $CONTAINER_IP. Setting API_HOST to IP."
      export API_HOST="$CONTAINER_IP" # Override API_HOST with the specific IP
    else
      echo "! Could not determine container IP. Using container name '$API_HOST' for API_HOST."
    fi
  else
    echo "! Container $MINERU_CONTAINER_NAME doesn't appear to be running"
  fi
else
  echo "! Docker command not found. Cannot check container status or IP."
fi

# Define the method used to restart the inference service ('docker', 'api', 'systemd', etc.)
# This tells the control script how to interact with the service.
export INFERENCE_SERVICE_TYPE="docker"

# Optional: Set Docker host if the socket is mounted differently or using TCP
if [ -e "/var/run/docker.sock" ]; then
  export DOCKER_HOST="unix:///var/run/docker.sock"
  echo "✓ Docker socket found at /var/run/docker.sock, enabling Docker API access via socket."
fi

echo "--- Environment variables set for mineru service control ---"
echo "DOCKER_COMPOSE_DIR: $DOCKER_COMPOSE_DIR"
echo "MINERU_CONTAINER_NAME: $MINERU_CONTAINER_NAME"
echo "API_HOST: $API_HOST (Use this address to reach the service API)"
echo "INFERENCE_SERVICE_TYPE: $INFERENCE_SERVICE_TYPE"
[ -n "$DOCKER_HOST" ] && echo "DOCKER_HOST: $DOCKER_HOST"
echo "-----------------------------------------------------------"

# Detailed Comments:
# DOCKER_COMPOSE_DIR: Specifies the directory where the docker-compose.yml file is located.
# DOCKER_COMPOSE_SERVICE: The service name as defined in the docker-compose.yml.
# MINERU_CONTAINER_NAME: The name of the Docker container running the service.
# API_HOST: The host address for the API, defaults to the container name.
# INFERENCE_SERVICE_TYPE: Method used to restart the service, default is 'docker'.
# DOCKER_HOST: Specifies the Docker host, used only if the Docker socket is located at /var/run/docker.sock.
#
# The script checks for the existence of the docker-compose.yml file and warns the user if it's not found.
# It attempts to detect the running status of the specified container and retrieves its IP address,
# updating the API_HOST variable accordingly. If the Docker command is not found, or the container is not running,
# it provides appropriate feedback to the user. Finally, it sets the DOCKER_HOST variable if the Docker socket is found
# at the default location, enabling communication with the Docker daemon.
