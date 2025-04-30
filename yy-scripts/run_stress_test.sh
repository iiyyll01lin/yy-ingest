#!/bin/bash
# Script to run stress tests using the find_optimal_semaphores.py script.
# Ensures necessary environment setup and Python package installations.

# Ensure we have the environment set up by sourcing the setup script
if [ -f "./setup_mineru_env.sh" ]; then
  source ./setup_mineru_env.sh
else
  echo "Warning: setup_mineru_env.sh not found. Using default environment variables."
  # Define default fallbacks if the setup script is missing
  export MINERU_CONTAINER_NAME="mineru"
  export API_HOST="mineru"
  export DOCKER_COMPOSE_DIR="/data/ssd1/mineru/doc-ingester"
fi

# Install Python3 and pip3 if not present
echo "Checking for Python and pip installation..."

# Set proxy for installations (if needed in the environment)
# Ensure this proxy is correct for your network configuration
export http_proxy="http://172.123.100.103:3128"
export https_proxy="http://172.123.100.103:3128"
echo "Setting proxy for package installations..."

# Check and install Python 3 using apt package manager
if ! command -v python3 &> /dev/null; then
  echo "Installing Python3..."
  apt update && apt install -y python3
fi

# Check and install pip3 using apt package manager
if ! command -v pip3 &> /dev/null; then
  echo "Installing pip3..."
  apt update && apt install -y python3-pip
fi

# Install required Python packages using pip3 if they are not already installed
# Checks are done by attempting to import the module in Python
echo "Checking for required packages..."
python3 -c "import docker" 2>/dev/null || pip3 install docker
python3 -c "import pandas" 2>/dev/null || pip3 install pandas
python3 -c "import matplotlib" 2>/dev/null || pip3 install matplotlib
python3 -c "import seaborn" 2>/dev/null || pip3 install seaborn
python3 -c "import tabulate" 2>/dev/null || pip3 install tabulate

# Unset proxy after installations are complete
echo "Unsetting proxy after installations..."
unset http_proxy
unset https_proxy

# Try to detect if the script is running inside a Docker container
if [ -f "/.dockerenv" ]; then
  echo "Running in a Docker container."

  # Check if the Docker socket is mounted, which is needed for Docker API interactions
  if [ -e "/var/run/docker.sock" ]; then
    echo "Docker socket is mounted. Docker API should work."
  else
    echo "Docker socket not mounted. Will rely on API health endpoints for service checks."
  fi
fi

# Run the main stress test Python script, passing any arguments received by this bash script
echo "Starting stress test..."
python3 find_optimal_semaphores.py "$@"
