#!/usr/bin/env python3
# Simple test script for the restart_inference_service function
# located in find_optimal_semaphores.py

import os
import sys
import time
import shutil
import requests
import subprocess

# Define API_HOST before importing the function, as it might be used during import
# This ensures the imported function uses the correct host setting.
API_HOST = os.environ.get("API_HOST", "mineru")  # Default to 'mineru' if not set

# Add the script's directory to the Python path to allow importing from sibling files
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import the specific function to be tested
try:
    from find_optimal_semaphores import restart_inference_service
except ImportError as e:
    print(f"Error importing restart_inference_service: {e}")
    print("Ensure find_optimal_semaphores.py is in the same directory or Python path.")
    sys.exit(1)

print("--- Testing restart_inference_service() --- ")

# Set environment variables required by the restart function for testing purposes
# These might override settings from setup_mineru_env.sh if sourced before running this.
os.environ["MINERU_CONTAINER_NAME"] = "mineru"  # Target container name
os.environ["API_HOST"] = "mineru"  # Target API host (can be name or IP)
os.environ["INFERENCE_SERVICE_TYPE"] = "docker"  # Specify restart method
# Ensure DOCKER_COMPOSE_DIR is set if using docker-compose based restart
# os.environ["DOCKER_COMPOSE_DIR"] = "/path/to/compose/dir"

print(f"Using MINERU_CONTAINER_NAME: {os.environ.get('MINERU_CONTAINER_NAME')}")
print(f"Using API_HOST: {os.environ.get('API_HOST')}")
print(f"Using INFERENCE_SERVICE_TYPE: {os.environ.get('INFERENCE_SERVICE_TYPE')}")

# Call the function to attempt the restart
print("\nAttempting to restart the service...")
result = restart_inference_service()

print(f"\nRestart function returned: {result}")
print("--- Test complete --- ")
