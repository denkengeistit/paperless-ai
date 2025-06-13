#!/bin/bash

# Paperless NGX Batch Processor Runner
# This script sets up the environment and runs the batch processor

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Paperless NGX Batch Processor${NC}"
echo "================================"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 is required but not installed.${NC}"
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is required but not installed.${NC}"
    exit 1
fi

# Check if batch_config.env exists
if [ ! -f "batch_config.env" ]; then
    echo -e "${YELLOW}Warning: batch_config.env not found.${NC}"
    if [ -f "batch_config.env.example" ]; then
        echo "Creating batch_config.env from example..."
        cp batch_config.env.example batch_config.env
        echo -e "${YELLOW}Please edit batch_config.env with your configuration before running again.${NC}"
        exit 1
    else
        echo -e "${RED}Error: No configuration file found.${NC}"
        exit 1
    fi
fi

# Source the batch configuration
echo "Loading configuration from batch_config.env..."
set -a  # automatically export all variables
source batch_config.env
set +a

# Validate required configuration
if [ -z "$PAPERLESS_URL" ] || [ -z "$PAPERLESS_TOKEN" ]; then
    echo -e "${RED}Error: PAPERLESS_URL and PAPERLESS_TOKEN must be set in batch_config.env${NC}"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Display configuration summary
echo ""
echo -e "${GREEN}Configuration Summary:${NC}"
echo "Paperless URL: $PAPERLESS_URL"
echo "Batch Size: ${BATCH_SIZE:-10}"
echo "OpenAI Tag: ${OPENAI_TAG_NAME:-0penAI}"
echo "Max Processing Time: ${MAX_PROCESSING_TIME:-1800} seconds"
echo ""

# Ask for confirmation
read -p "Start batch processing? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Run the batch processor
echo -e "${GREEN}Starting batch processor...${NC}"
echo "Logs will be written to batch_processor.log"
echo "Press Ctrl+C to stop gracefully"
echo ""

# Make sure the script is executable
chmod +x batch_processor.py

# Run the batch processor
python3 batch_processor.py

echo -e "${GREEN}Batch processor finished.${NC}"