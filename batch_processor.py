#!/usr/bin/env python3
"""
Paperless NGX Batch Processing Automation Script

This script orchestrates the batch processing of documents in Paperless NGX
that don't have Document Types and Correspondents assigned using Paperless AI.

Features:
- Finds documents without document_type and correspondent
- Processes them in small batches to avoid overwhelming the system
- Automatically manages the "0penAI" tag for filtering
- Starts/stops the Paperless AI server for each batch
- Monitors processing status to know when a batch is complete
"""

import os
import sys
import json
import time
import signal
import subprocess
import requests
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_processor.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingConfig:
    """Configuration for batch processing"""
    paperless_url: str
    paperless_token: str
    paperless_ai_url: str = "http://localhost:3000"
    openai_tag_name: str = "0penAI"
    batch_size: int = 10
    max_processing_time: int = 1800  # 30 minutes max per batch
    polling_interval: int = 30  # Check status every 30 seconds
    server_startup_wait: int = 60  # Wait 60 seconds for server to start

class PaperlessAPI:
    """Handles communication with Paperless NGX API"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {config.paperless_token}',
            'Content-Type': 'application/json'
        })
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make API request with error handling"""
        url = f"{self.config.paperless_url}/api{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"API request failed: {method} {url} - {e}")
            raise
    
    def get_documents_without_types_and_correspondents(self) -> List[Dict]:
        """Get documents that don't have document_type or correspondent assigned"""
        logger.info("Fetching documents without document types and correspondents...")
        
        documents = []
        page = 1
        
        while True:
            params = {
                'page': page,
                'page_size': 100,
                'document_type__isnull': True,
                'correspondent__isnull': True,
                'fields': 'id,title,created,document_type,correspondent,tags'
            }
            
            response = self._make_request('GET', '/documents/', params=params)
            data = response.json()
            
            page_documents = data.get('results', [])
            if not page_documents:
                break
                
            # Filter documents that truly don't have both document_type AND correspondent
            filtered_docs = [
                doc for doc in page_documents 
                if doc.get('document_type') is None and doc.get('correspondent') is None
            ]
            
            documents.extend(filtered_docs)
            
            if not data.get('next'):
                break
                
            page += 1
            
        logger.info(f"Found {len(documents)} documents without document types and correspondents")
        return documents
    
    def get_or_create_tag(self, tag_name: str) -> Dict:
        """Get existing tag or create new one"""
        # Search for existing tag
        response = self._make_request('GET', '/tags/', params={'name__iexact': tag_name})
        results = response.json().get('results', [])
        
        if results:
            logger.info(f"Found existing tag '{tag_name}' with ID {results[0]['id']}")
            return results[0]
        
        # Create new tag
        response = self._make_request('POST', '/tags/', json={'name': tag_name})
        tag = response.json()
        logger.info(f"Created new tag '{tag_name}' with ID {tag['id']}")
        return tag
    
    def add_tag_to_documents(self, document_ids: List[int], tag_id: int) -> None:
        """Add tag to multiple documents"""
        logger.info(f"Adding tag {tag_id} to {len(document_ids)} documents...")
        
        for doc_id in document_ids:
            try:
                # Get current document data
                response = self._make_request('GET', f'/documents/{doc_id}/')
                doc_data = response.json()
                
                # Add tag if not already present
                current_tags = doc_data.get('tags', [])
                if tag_id not in current_tags:
                    current_tags.append(tag_id)
                    
                    # Update document
                    update_data = {'tags': current_tags}
                    self._make_request('PUT', f'/documents/{doc_id}/', json=update_data)
                    logger.debug(f"Added tag to document {doc_id}")
                else:
                    logger.debug(f"Document {doc_id} already has the tag")
                    
            except Exception as e:
                logger.error(f"Failed to add tag to document {doc_id}: {e}")
    
    def remove_tag_from_documents(self, document_ids: List[int], tag_id: int) -> None:
        """Remove tag from multiple documents"""
        logger.info(f"Removing tag {tag_id} from {len(document_ids)} documents...")
        
        for doc_id in document_ids:
            try:
                # Get current document data
                response = self._make_request('GET', f'/documents/{doc_id}/')
                doc_data = response.json()
                
                # Remove tag if present
                current_tags = doc_data.get('tags', [])
                if tag_id in current_tags:
                    current_tags.remove(tag_id)
                    
                    # Update document
                    update_data = {'tags': current_tags}
                    self._make_request('PUT', f'/documents/{doc_id}/', json=update_data)
                    logger.debug(f"Removed tag from document {doc_id}")
                    
            except Exception as e:
                logger.error(f"Failed to remove tag from document {doc_id}: {e}")
    
    def check_documents_processed(self, document_ids: List[int]) -> bool:
        """Check if documents have been processed (have document_type or correspondent)"""
        processed_count = 0
        
        for doc_id in document_ids:
            try:
                response = self._make_request('GET', f'/documents/{doc_id}/')
                doc_data = response.json()
                
                # Check if document now has document_type OR correspondent
                if doc_data.get('document_type') is not None or doc_data.get('correspondent') is not None:
                    processed_count += 1
                    logger.debug(f"Document {doc_id} has been processed")
                    
            except Exception as e:
                logger.error(f"Failed to check document {doc_id}: {e}")
        
        logger.info(f"Processed documents: {processed_count}/{len(document_ids)}")
        return processed_count == len(document_ids)

class PaperlessAIController:
    """Controls the Paperless AI server"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        
    def start_server(self) -> bool:
        """Start the Paperless AI server"""
        logger.info("Starting Paperless AI server...")
        
        try:
            # Start the server using npm
            self.process = subprocess.Popen(
                ['npm', 'start'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Wait for server to start up
            logger.info(f"Waiting {self.config.server_startup_wait} seconds for server to start...")
            time.sleep(self.config.server_startup_wait)
            
            # Check if server is responding
            if self._check_server_health():
                logger.info("Paperless AI server started successfully")
                return True
            else:
                logger.error("Server failed to start or not responding")
                self.stop_server()
                return False
                
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def stop_server(self) -> None:
        """Stop the Paperless AI server"""
        if self.process:
            logger.info("Stopping Paperless AI server...")
            
            try:
                # Send SIGTERM first
                self.process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop gracefully
                    logger.warning("Server didn't stop gracefully, forcing termination...")
                    self.process.kill()
                    self.process.wait()
                
                logger.info("Paperless AI server stopped")
                
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
            
            finally:
                self.process = None
    
    def _check_server_health(self) -> bool:
        """Check if the server is responding"""
        try:
            response = requests.get(f"{self.config.paperless_ai_url}/health", timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_processing_status(self) -> Dict:
        """Get current processing status from the server"""
        try:
            response = requests.get(f"{self.config.paperless_ai_url}/api/status", timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {'isProcessing': False}

class BatchProcessor:
    """Main batch processing orchestrator"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.api = PaperlessAPI(config)
        self.ai_controller = PaperlessAIController(config)
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.ai_controller.stop_server()
    
    def process_batch(self, documents: List[Dict], openai_tag: Dict) -> bool:
        """Process a single batch of documents"""
        batch_doc_ids = [doc['id'] for doc in documents]
        logger.info(f"Processing batch of {len(batch_doc_ids)} documents: {batch_doc_ids}")
        
        try:
            # Add OpenAI tag to documents
            self.api.add_tag_to_documents(batch_doc_ids, openai_tag['id'])
            
            # Start Paperless AI server
            if not self.ai_controller.start_server():
                logger.error("Failed to start Paperless AI server")
                return False
            
            # Monitor processing
            start_time = time.time()
            max_time = self.config.max_processing_time
            
            while self.running:
                # Check if processing is complete
                if self.api.check_documents_processed(batch_doc_ids):
                    logger.info("All documents in batch have been processed")
                    break
                
                # Check timeout
                if time.time() - start_time > max_time:
                    logger.warning(f"Batch processing timed out after {max_time} seconds")
                    break
                
                # Check server status
                status = self.ai_controller.get_processing_status()
                if status.get('isProcessing'):
                    logger.info("Server is actively processing documents...")
                
                # Wait before next check
                time.sleep(self.config.polling_interval)
            
            return True
            
        finally:
            # Clean up: stop server and remove tag
            self.ai_controller.stop_server()
            self.api.remove_tag_from_documents(batch_doc_ids, openai_tag['id'])
            
            # Wait a bit before next batch
            if self.running:
                logger.info("Waiting 30 seconds before next batch...")
                time.sleep(30)
    
    def run(self) -> None:
        """Main processing loop"""
        logger.info("Starting batch processor...")
        
        try:
            # Get or create the OpenAI tag
            openai_tag = self.api.get_or_create_tag(self.config.openai_tag_name)
            
            batch_count = 0
            
            while self.running:
                # Get documents that need processing
                unprocessed_docs = self.api.get_documents_without_types_and_correspondents()
                
                if not unprocessed_docs:
                    logger.info("No more documents to process. Exiting.")
                    break
                
                # Process in batches
                for i in range(0, len(unprocessed_docs), self.config.batch_size):
                    if not self.running:
                        break
                        
                    batch = unprocessed_docs[i:i + self.config.batch_size]
                    batch_count += 1
                    
                    logger.info(f"Starting batch {batch_count} ({len(batch)} documents)")
                    
                    success = self.process_batch(batch, openai_tag)
                    if not success:
                        logger.error(f"Batch {batch_count} failed")
                        # Continue to next batch instead of stopping completely
                        continue
                    
                    logger.info(f"Batch {batch_count} completed successfully")
                
                # Check if there are still unprocessed documents
                remaining_docs = self.api.get_documents_without_types_and_correspondents()
                if not remaining_docs:
                    logger.info("All documents have been processed!")
                    break
                else:
                    logger.info(f"{len(remaining_docs)} documents still need processing")
            
        except Exception as e:
            logger.error(f"Unexpected error in main processing loop: {e}")
            raise
        finally:
            # Ensure server is stopped
            self.ai_controller.stop_server()
            logger.info("Batch processor finished")

def load_config() -> ProcessingConfig:
    """Load configuration from environment variables or .env file"""
    
    # Try to load from .env file if it exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # Also try the data/.env file
    data_env_file = os.path.join(os.path.dirname(__file__), 'data', '.env')
    if os.path.exists(data_env_file):
        with open(data_env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # Get required configuration
    paperless_url = (
        os.getenv('PAPERLESS_API_URL') or 
        os.getenv('PAPERLESS_URL') or 
        os.getenv('PAPERLESS_NGX_URL') or 
        os.getenv('PAPERLESS_HOST')
    )
    
    paperless_token = (
        os.getenv('PAPERLESS_TOKEN') or 
        os.getenv('PAPERLESS_API_TOKEN') or 
        os.getenv('PAPERLESS_APIKEY')
    )
    
    if not paperless_url or not paperless_token:
        logger.error("Missing required Paperless NGX configuration!")
        logger.error("Please set PAPERLESS_URL and PAPERLESS_TOKEN environment variables")
        sys.exit(1)
    
    # Remove /api suffix if present
    if paperless_url.endswith('/api'):
        paperless_url = paperless_url[:-4]
    
    return ProcessingConfig(
        paperless_url=paperless_url,
        paperless_token=paperless_token,
        paperless_ai_url=os.getenv('PAPERLESS_AI_URL', 'http://localhost:3000'),
        openai_tag_name=os.getenv('OPENAI_TAG_NAME', '0penAI'),
        batch_size=int(os.getenv('BATCH_SIZE', '10')),
        max_processing_time=int(os.getenv('MAX_PROCESSING_TIME', '1800')),
        polling_interval=int(os.getenv('POLLING_INTERVAL', '30')),
        server_startup_wait=int(os.getenv('SERVER_STARTUP_WAIT', '60'))
    )

def main():
    """Main entry point"""
    try:
        config = load_config()
        
        logger.info("Paperless NGX Batch Processor")
        logger.info(f"Paperless URL: {config.paperless_url}")
        logger.info(f"Batch size: {config.batch_size}")
        logger.info(f"OpenAI tag: {config.openai_tag_name}")
        
        processor = BatchProcessor(config)
        processor.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()