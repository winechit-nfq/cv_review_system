"""
Google Drive Webhook Handler for Automatic CV Review
This module handles Google Drive push notifications to automatically trigger CV reviews
when new files are uploaded to monitored folders.
"""

import os
import json
import hashlib
import hmac
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, BackgroundTasks
from googleapiclient.discovery import build
from google.oauth2 import service_account
import asyncio
from datetime import datetime
import logging

from .cv_utils import (
    get_gdrive_cv_content, 
    run_openai_review, 
    get_job_description_from_drive,
    extract_fit_score,
    move_to_qualified_folder
)
from .models import ReviewAllResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DriveWebhookHandler:
    def __init__(self):
        self.monitored_folders = {}  # folder_id -> position_name mapping
        self.webhook_channels = {}   # channel_id -> folder_info mapping
        
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
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/drive.file"
            ]
        )
        return build('drive', 'v3', credentials=creds)

    async def setup_webhook_for_folder(self, folder_id: str, position_name: str) -> Dict[str, Any]:
        """
        Setup a webhook to monitor a specific Google Drive folder for file uploads.
        
        Args:
            folder_id: The Google Drive folder ID to monitor
            position_name: The position name (for context)
            
        Returns:
            Dictionary with channel information
        """
        try:
            service = self.setup_drive_service()
            
            # Generate unique channel ID
            channel_id = f"cv_review_{folder_id}_{int(datetime.now().timestamp())}"
            
            # Your webhook endpoint URL (update this with your actual domain)
            webhook_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com") + "/webhook/drive"
            
            # Create watch request
            body = {
                'id': channel_id,
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True
            }
            
            # Setup the watch
            response = service.files().watch(
                fileId=folder_id,
                body=body
            ).execute()
            
            # Store channel information
            self.webhook_channels[channel_id] = {
                'folder_id': folder_id,
                'position_name': position_name,
                'resource_id': response.get('resourceId'),
                'expiration': response.get('expiration')
            }
            
            self.monitored_folders[folder_id] = position_name
            
            logger.info(f"Webhook setup for folder {folder_id} ({position_name}): {response}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to setup webhook for folder {folder_id}: {str(e)}")
            raise

    async def handle_drive_notification(self, request: Request, background_tasks: BackgroundTasks):
        """
        Handle incoming Google Drive push notifications.
        
        Args:
            request: FastAPI request object containing the webhook payload
            background_tasks: FastAPI background tasks for async processing
        """
        try:
            # Get headers
            headers = dict(request.headers)
            channel_id = headers.get('x-goog-channel-id')
            resource_state = headers.get('x-goog-resource-state')
            
            logger.info(f"Received webhook: channel={channel_id}, state={resource_state}")
            
            # Only process 'update' events (file additions/modifications)
            if resource_state not in ['update', 'sync']:
                return {"status": "ignored", "reason": f"State {resource_state} not processed"}
            
            # Verify the channel is one we're monitoring
            if channel_id not in self.webhook_channels:
                logger.warning(f"Unknown channel ID: {channel_id}")
                return {"status": "ignored", "reason": "Unknown channel"}
            
            channel_info = self.webhook_channels[channel_id]
            folder_id = channel_info['folder_id']
            position_name = channel_info['position_name']
            
            # Add background task to process new files
            background_tasks.add_task(
                self.process_new_files_in_folder,
                folder_id,
                position_name
            )
            
            return {"status": "accepted", "folder_id": folder_id}
            
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def process_new_files_in_folder(self, folder_id: str, position_name: str):
        """
        Process new CV files in a monitored folder.
        
        Args:
            folder_id: Google Drive folder ID containing CVs
            position_name: Position name for context
        """
        try:
            logger.info(f"Processing new files in folder {folder_id} ({position_name})")
            
            service = self.setup_drive_service()
            
            # Get recently added files (last 5 minutes)
            from datetime import datetime, timedelta
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            time_filter = five_minutes_ago.isoformat() + 'Z'
            
            # Query for recent PDF/DOCX files
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
            
            if not new_files:
                logger.info(f"No new CV files found in folder {folder_id}")
                return
            
            logger.info(f"Found {len(new_files)} new CV files to process")
            
            # Get job description for this position
            # Assuming job description is in a sibling folder
            parent_folder_response = service.files().get(
                fileId=folder_id,
                fields="parents"
            ).execute()
            
            if parent_folder_response.get('parents'):
                parent_folder_id = parent_folder_response['parents'][0]
                
                # Look for job_description subfolder
                job_desc_query = (
                    f"'{parent_folder_id}' in parents and "
                    f"mimeType='application/vnd.google-apps.folder' and "
                    f"name='job_description' and "
                    f"trashed=false"
                )
                
                job_desc_folders = service.files().list(q=job_desc_query).execute()
                job_desc_folder_id = None
                
                if job_desc_folders.get('files'):
                    job_desc_folder_id = job_desc_folders['files'][0]['id']
                
                # Get job description content
                job_description = ""
                if job_desc_folder_id:
                    job_description = get_job_description_from_drive(job_desc_folder_id)
                
                # Find qualified folder
                qualified_query = (
                    f"'{parent_folder_id}' in parents and "
                    f"mimeType='application/vnd.google-apps.folder' and "
                    f"name='qualified_cv_list' and "
                    f"trashed=false"
                )
                
                qualified_folders = service.files().list(q=qualified_query).execute()
                qualified_folder_id = None
                
                if qualified_folders.get('files'):
                    qualified_folder_id = qualified_folders['files'][0]['id']
                
                # Process each new file
                for file_info in new_files:
                    await self.process_single_cv(
                        file_info, 
                        job_description, 
                        qualified_folder_id,
                        position_name
                    )
                    
        except Exception as e:
            logger.error(f"Error processing files in folder {folder_id}: {str(e)}")

    async def process_single_cv(
        self, 
        file_info: Dict[str, Any], 
        job_description: str, 
        qualified_folder_id: Optional[str],
        position_name: str
    ):
        """
        Process a single CV file automatically.
        
        Args:
            file_info: Dictionary containing file id, name, etc.
            job_description: Job description text
            qualified_folder_id: ID of folder to move qualified CVs
            position_name: Position name for logging
        """
        try:
            file_id = file_info['id']
            file_name = file_info['name']
            
            logger.info(f"Auto-processing CV: {file_name} for position: {position_name}")
            
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
            
            # Log the result
            logger.info(f"Auto-review completed for {file_name}: Score={fit_score}, Moved={moved_to_qualified}")
            
            # Optional: Store result in database or send notification
            await self.notify_review_completed(result, position_name, moved_to_qualified)
            
        except Exception as e:
            logger.error(f"Error processing CV {file_info.get('name', 'unknown')}: {str(e)}")

    async def notify_review_completed(
        self, 
        result: ReviewAllResult, 
        position_name: str, 
        moved_to_qualified: bool
    ):
        """
        Send notification about completed review.
        You can customize this to send emails, Slack messages, etc.
        
        Args:
            result: Review result object
            position_name: Position name
            moved_to_qualified: Whether CV was moved to qualified folder
        """
        logger.info(
            f"NOTIFICATION: CV '{result.cv_name}' reviewed for {position_name}. "
            f"Score: {result.fit_score}. "
            f"{'Moved to qualified folder.' if moved_to_qualified else 'Not qualified.'}"
        )
        
        # TODO: Add email/Slack/webhook notifications here
        # Example:
        # await send_email_notification(result, position_name)
        # await send_slack_notification(result, position_name)

    async def stop_webhook_for_folder(self, channel_id: str):
        """
        Stop monitoring a folder by stopping the webhook channel.
        
        Args:
            channel_id: The channel ID to stop
        """
        try:
            service = self.setup_drive_service()
            
            if channel_id in self.webhook_channels:
                channel_info = self.webhook_channels[channel_id]
                
                # Stop the channel
                service.channels().stop(
                    body={
                        'id': channel_id,
                        'resourceId': channel_info['resource_id']
                    }
                ).execute()
                
                # Remove from tracking
                folder_id = channel_info['folder_id']
                del self.webhook_channels[channel_id]
                if folder_id in self.monitored_folders:
                    del self.monitored_folders[folder_id]
                
                logger.info(f"Stopped webhook for channel {channel_id}")
                
        except Exception as e:
            logger.error(f"Error stopping webhook {channel_id}: {str(e)}")

# Global instance
webhook_handler = DriveWebhookHandler()
