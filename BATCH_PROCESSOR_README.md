# Paperless NGX Batch Processor

This batch processor automates the processing of documents in your Paperless NGX instance that don't have Document Types and Correspondents assigned. It orchestrates your Paperless AI fork to process documents in small batches, reducing the load on your system and eliminating the need for manual intervention.

## Features

- 🔍 **Automatic Discovery**: Finds documents without document types and correspondents
- 📦 **Batch Processing**: Processes documents in configurable small batches (default: 10 documents)
- 🏷️ **Tag Management**: Automatically manages the "0penAI" tag for filtering
- 🖥️ **Server Control**: Starts and stops your Paperless AI server automatically for each batch
- 📊 **Progress Monitoring**: Monitors processing status and knows when batches are complete
- 🛡️ **Error Handling**: Robust error handling and graceful shutdowns
- 📝 **Comprehensive Logging**: Detailed logs for monitoring and debugging

## How It Works

1. **Discovery**: The processor queries your Paperless NGX API to find documents that don't have both `document_type` and `correspondent` assigned
2. **Batch Creation**: Groups these documents into small batches (default: 10 documents)
3. **Tag Application**: Adds the "0penAI" tag to documents in the current batch
4. **Server Startup**: Starts your Paperless AI server (configured to process documents with the "0penAI" tag)
5. **Monitoring**: Continuously monitors the processing status until all documents in the batch are processed
6. **Cleanup**: Stops the server, removes the tag from processed documents
7. **Repeat**: Moves to the next batch and repeats the process

## Prerequisites

- Python 3.8 or higher
- Node.js and npm
- Your Paperless AI fork (this repository)
- Paperless NGX instance with API access

## Setup

### 1. Clone and Navigate to Your Repository

Make sure you're in your Paperless AI repository directory.

### 2. Configure the Batch Processor

Copy the example configuration file:

```bash
cp batch_config.env.example batch_config.env
```

Edit `batch_config.env` with your settings:

```bash
# Required: Paperless NGX API Configuration
PAPERLESS_URL=http://your-paperless-instance:8000
PAPERLESS_TOKEN=your_paperless_api_token_here

# Optional: Customize batch processing
BATCH_SIZE=10                    # Number of documents per batch
MAX_PROCESSING_TIME=1800         # Maximum time per batch (30 minutes)
POLLING_INTERVAL=30              # Check status every 30 seconds
OPENAI_TAG_NAME=0penAI          # Tag name for filtering
```

### 3. Configure Your Paperless AI

Make sure your main Paperless AI configuration (in `.env` or `data/.env`) includes:

```bash
# Process only documents with specific tags
PROCESS_PREDEFINED_DOCUMENTS=yes
TAGS=0penAI

# Your AI provider settings
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Your Paperless NGX API settings
PAPERLESS_URL=http://your-paperless-instance:8000
PAPERLESS_TOKEN=your_paperless_api_token_here
```

## Usage

### Quick Start

Run the batch processor with the included script:

```bash
./run_batch_processor.sh
```

This script will:
- Check dependencies
- Set up Python virtual environment
- Install required packages
- Show configuration summary
- Start the batch processing

### Manual Execution

If you prefer to run manually:

```bash
# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Load configuration and run
source batch_config.env
python3 batch_processor.py
```

### Monitoring Progress

The processor provides real-time feedback:

```
2024-01-15 10:30:00 - INFO - Found 247 documents without document types and correspondents
2024-01-15 10:30:00 - INFO - Starting batch 1 (10 documents)
2024-01-15 10:30:00 - INFO - Adding tag 15 to 10 documents...
2024-01-15 10:30:05 - INFO - Starting Paperless AI server...
2024-01-15 10:31:05 - INFO - Paperless AI server started successfully
2024-01-15 10:31:35 - INFO - Server is actively processing documents...
2024-01-15 10:32:05 - INFO - Processed documents: 7/10
2024-01-15 10:32:35 - INFO - All documents in batch have been processed
2024-01-15 10:32:40 - INFO - Stopping Paperless AI server...
2024-01-15 10:32:45 - INFO - Batch 1 completed successfully
```

### Logs

All activity is logged to:
- **Console**: Real-time progress updates
- **batch_processor.log**: Detailed log file for review

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `BATCH_SIZE` | 10 | Number of documents to process in each batch |
| `MAX_PROCESSING_TIME` | 1800 | Maximum time (seconds) to wait for batch completion |
| `POLLING_INTERVAL` | 30 | How often (seconds) to check processing status |
| `SERVER_STARTUP_WAIT` | 60 | Time (seconds) to wait for server startup |
| `OPENAI_TAG_NAME` | 0penAI | Tag name used for filtering documents |

## Troubleshooting

### Common Issues

#### "No documents found"
- Check that you have documents without document types AND correspondents
- Verify your Paperless NGX API connection and token

#### "Server failed to start"
- Check that port 3000 is available
- Verify Node.js dependencies are installed (`npm install`)
- Check your Paperless AI configuration in `.env`

#### "Processing timeout"
- Increase `MAX_PROCESSING_TIME` for larger batches
- Check Paperless AI logs for processing errors
- Verify your AI provider (OpenAI) is responding

#### "API request failed"
- Verify `PAPERLESS_URL` and `PAPERLESS_TOKEN` in configuration
- Check Paperless NGX is running and accessible
- Ensure API token has sufficient permissions

### Debug Mode

For more detailed logging, you can modify the log level in `batch_processor.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    # ... rest of config
)
```

### Manual Recovery

If processing is interrupted:

1. Check which documents still have the "0penAI" tag in Paperless NGX
2. Remove the tag from any documents that weren't processed
3. Restart the batch processor

## Safety Features

- **Graceful Shutdown**: Ctrl+C cleanly stops processing and cleans up
- **Tag Cleanup**: Always removes processing tags, even on failure
- **Server Management**: Ensures AI server is stopped between batches
- **Error Recovery**: Continues with next batch if one batch fails
- **Progress Tracking**: Detailed logging for monitoring and recovery

## Advanced Usage

### Custom Filtering

You can modify the document filtering criteria in `batch_processor.py`:

```python
def get_documents_without_types_and_correspondents(self) -> List[Dict]:
    # Modify the params to change filtering criteria
    params = {
        'page': page,
        'page_size': 100,
        'document_type__isnull': True,     # Only documents without type
        'correspondent__isnull': True,     # Only documents without correspondent
        # Add more filters as needed
    }
```

### Integration with Cron

For automated processing, you can set up a cron job:

```bash
# Run batch processor daily at 2 AM
0 2 * * * cd /path/to/paperless-ai && ./run_batch_processor.sh >> /var/log/batch_processor_cron.log 2>&1
```

## Performance Recommendations

- **Batch Size**: Start with 10 documents per batch. Increase gradually based on your system performance
- **Processing Time**: Monitor average processing time and adjust `MAX_PROCESSING_TIME` accordingly
- **System Resources**: Ensure adequate CPU and memory for both Paperless AI and NGX during processing
- **Network**: Stable connection between batch processor, Paperless NGX, and AI provider

## Support

If you encounter issues:

1. Check the logs in `batch_processor.log`
2. Verify your configuration in `batch_config.env`
3. Test your Paperless AI setup manually first
4. Check Paperless NGX API access and permissions

## Contributing

This batch processor is designed to work with your specific Paperless AI fork. Modifications and improvements are welcome!

---

**Happy automated document processing! 🚀**