"""
Polling-based Auto CV Processor
Alternative to webhooks - periodically checks for new CV files and processes them automatically
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
import json

from .cv_utils import (
    get_gdrive_cv_content,
    run_openai_review,
    get_job_description_from_drive,
    extract_fit_score,
    move_to_qualified_folder
)
from .models import ReviewAllResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoCVProcessor:
    def __init__(self):
        self.monitored_folders = {}  # folder_id -> position_name
        self.processed_files = set()  # Set of file IDs we've already processed
        self.is_running = False
        self.check_interval = 300  # Check every 5 minutes
        
    def setup_drive_service(self):
        """Setup Google Drive service with credentials."""
        creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        if not creds_json:
            raise Exception("Google Drive credentials not configured")
        
        if creds_json.strip().startswith('{'):
            creds_dict = json.loads(creds_json)
        else:
            with open(creds_json) as f:
                creds_dict = json.load(f)
                
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build('drive', 'v3', credentials=creds)

    async def add_folder_to_monitor(self, folder_id: str, position_name: str):
        """Add a folder to the monitoring list."""
        self.monitored_folders[folder_id] = position_name
        logger.info(f"Added folder {folder_id} ({position_name}) to monitoring")
        
        # Initialize with existing files to avoid reprocessing
        await self.initialize_existing_files(folder_id)

    def remove_folder_from_monitor(self, folder_id: str):
        """Remove a folder from monitoring."""
        if folder_id in self.monitored_folders:
            position_name = self.monitored_folders[folder_id]
            del self.monitored_folders[folder_id]
            logger.info(f"Removed folder {folder_id} ({position_name}) from monitoring")

    async def initialize_existing_files(self, folder_id: str):
        """Mark existing files as processed to avoid reprocessing them."""
        try:
            service = self.setup_drive_service()
            
            # Get all existing CV files
            query = (
                f"'{folder_id}' in parents and "
                f"(mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and "
                f"trashed=false"
            )
            
            results = service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            for file_info in files:
                self.processed_files.add(file_info['id'])
                
            logger.info(f"Initialized {len(files)} existing files for folder {folder_id}")
            
        except Exception as e:
            logger.error(f"Error initializing existing files for folder {folder_id}: {str(e)}")

    async def start_monitoring(self):
        """Start the monitoring loop."""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return
            
        self.is_running = True
        logger.info(f"Starting auto CV processing monitor (checking every {self.check_interval} seconds)")
        
        while self.is_running:
            try:
                await self.check_for_new_files()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.is_running = False
        logger.info("Stopped auto CV processing monitor")

    async def check_for_new_files(self):
        """Check all monitored folders for new CV files."""
        if not self.monitored_folders:
            return
            
        logger.debug(f"Checking {len(self.monitored_folders)} monitored folders for new files")
        
        for folder_id, position_name in self.monitored_folders.items():
            try:
                await self.check_folder_for_new_files(folder_id, position_name)
            except Exception as e:
                logger.error(f"Error checking folder {folder_id} ({position_name}): {str(e)}")

    async def check_folder_for_new_files(self, folder_id: str, position_name: str):
        """Check a specific folder for new CV files."""
        try:
            service = self.setup_drive_service()
            
            # Look for files created in the last check interval + buffer
            buffer_minutes = 10  # Extra buffer to catch files
            since_time = datetime.utcnow() - timedelta(seconds=self.check_interval + buffer_minutes * 60)
            time_filter = since_time.isoformat() + 'Z'
            
            # Query for recent CV files
            query = (
                f"'{folder_id}' in parents and "
                f"(mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and "
                f"createdTime > '{time_filter}' and "
                f"trashed=false"
            )
            
            results = service.files().list(
                q=query,
                fields="files(id, name, createdTime)",
                orderBy="createdTime desc"
            ).execute()
            
            new_files = results.get('files', [])
            
            # Filter out files we've already processed
            truly_new_files = [
                f for f in new_files 
                if f['id'] not in self.processed_files
            ]
            
            if not truly_new_files:
                return
                
            logger.info(f"Found {len(truly_new_files)} new CV files in {position_name}")
            
            # Get job description and qualified folder for this position
            parent_folder_response = service.files().get(
                fileId=folder_id,
                fields="parents"
            ).execute()
            
            job_description = ""
            qualified_folder_id = None
            
            if parent_folder_response.get('parents'):
                parent_folder_id = parent_folder_response['parents'][0]
                
                # Get job description
                job_desc_query = (
                    f"'{parent_folder_id}' in parents and "
                    f"mimeType='application/vnd.google-apps.folder' and "
                    f"name='job_description' and "
                    f"trashed=false"
                )
                
                job_desc_folders = service.files().list(q=job_desc_query).execute()
                if job_desc_folders.get('files'):
                    job_desc_folder_id = job_desc_folders['files'][0]['id']
                    job_description = get_job_description_from_drive(job_desc_folder_id)
                
                # Get qualified folder
                qualified_query = (
                    f"'{parent_folder_id}' in parents and "
                    f"mimeType='application/vnd.google-apps.folder' and "
                    f"name='qualified_cv_list' and "
                    f"trashed=false"
                )
                
                qualified_folders = service.files().list(q=qualified_query).execute()
                if qualified_folders.get('files'):
                    qualified_folder_id = qualified_folders['files'][0]['id']
            
            # Process each new file
            for file_info in truly_new_files:
                try:
                    await self.process_single_cv(
                        file_info,
                        job_description,
                        qualified_folder_id,
                        position_name
                    )
                    # Mark as processed
                    self.processed_files.add(file_info['id'])
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_info['name']}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error checking folder {folder_id} for new files: {str(e)}")

    async def process_single_cv(
        self,
        file_info: Dict,
        job_description: str,
        qualified_folder_id: str,
        position_name: str
    ):
        """Process a single CV file automatically."""
        file_id = file_info['id']
        file_name = file_info['name']
        
        logger.info(f"Auto-processing CV: {file_name} for position: {position_name}")
        
        try:
            # Extract CV content
            cv_text = get_gdrive_cv_content(file_id)
            
            # Run AI review
            review_output = run_openai_review(cv_text, file_name, job_description)
            review = review_output.raw if hasattr(review_output, "raw") else str(review_output)
            
            # Extract fit score
            fit_score = extract_fit_score(review)
            
            # Get token usage
            token_usage = getattr(review_output, "token_usage", None)
            if token_usage and hasattr(token_usage, "prompt_tokens"):
                prompt_tokens = token_usage.prompt_tokens
                completion_tokens = token_usage.completion_tokens
                total_tokens = token_usage.total_tokens
            else:
                total_tokens = len(review.split()) * 2
                prompt_tokens = len(cv_text.split())
                completion_tokens = total_tokens - prompt_tokens
            
            # Create result object
            result = ReviewAllResult(
                cv_name=file_name,
                review=review,
                fit_score=fit_score,
                token_count=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
            # Auto-move qualified candidates
            moved_to_qualified = False
            if fit_score > 80 and qualified_folder_id:
                moved_to_qualified = move_to_qualified_folder(file_id, qualified_folder_id)
                if moved_to_qualified:
                    logger.info(f"Auto-moved qualified CV {file_name} to qualified folder")
            
            # Log completion
            logger.info(
                f"Auto-review completed for {file_name}: "
                f"Score={fit_score}, Moved={moved_to_qualified}"
            )
            
            # Optional: Send notification
            await self.send_notification(result, position_name, moved_to_qualified)
            
        except Exception as e:
            logger.error(f"Error processing CV {file_name}: {str(e)}")

    async def send_notification(
        self,
        result: ReviewAllResult,
        position_name: str,
        moved_to_qualified: bool
    ):
        """Send notification about completed review."""
        logger.info(
            f"NOTIFICATION: CV '{result.cv_name}' reviewed for {position_name}. "
            f"Score: {result.fit_score}. "
            f"{'Moved to qualified folder.' if moved_to_qualified else 'Not qualified.'}"
        )

    def get_status(self):
        """Get current monitoring status."""
        return {
            "is_running": self.is_running,
            "monitored_folders": self.monitored_folders,
            "processed_files_count": len(self.processed_files),
            "check_interval_seconds": self.check_interval
        }

# Global instance
auto_processor = AutoCVProcessor()
