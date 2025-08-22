import os
from fastapi import FastAPI, Query, Body, Request, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
from google.oauth2 import service_account
from github import Github
from fastapi.responses import PlainTextResponse
import base64
from crewai import Crew, Agent, Task
import re
import json
from backend.crew import CrewAI
import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
from pdfminer.high_level import extract_text
from backend.models import CVInfo, ReviewResult, ReviewAllResult
from backend.cv_utils import (
    get_gdrive_cv_content,
    get_github_cv_content,
    run_openai_review,
    run_gemini_review,
    extract_fit_score,
    move_to_qualified_folder,
    get_job_description_from_drive,
    get_file_content
)
from backend.webhook_handler import webhook_handler
from backend.auto_processor import auto_processor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def list_gdrive_folders(parent_id: str = None):
    creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
    root_folder_id = parent_id if parent_id is not None else os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not creds_json or not root_folder_id:
        return []
    
    if creds_json.strip().startswith('{'):
        creds_dict = json.loads(creds_json)
    else:
        with open(creds_json) as f:
            creds_dict = json.load(f)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive"])
    service = build('drive', 'v3', credentials=creds)

    try:
        # Query for folders within the root folder
        results = service.files().list(
            q=f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)",
            pageSize=50
        ).execute()
        folders = results.get('files', [])
        return [{"id": folder["id"], "name": folder["name"]} for folder in folders]
    except Exception as e:
        print(f"Error listing folders: {e}")
        return []

def list_gdrive_cvs(folder_id=None):
    creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
    if not folder_id:
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not creds_json or not folder_id:
        return []
    
    if creds_json.strip().startswith('{'):
        creds_dict = json.loads(creds_json)
    else:
        with open(creds_json) as f:
            creds_dict = json.load(f)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive"])
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(
        q=f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed=false",
        fields="files(id, name)",
        pageSize=50
    ).execute()
    files = results.get('files', [])
    return [CVInfo(name=f["name"], source="gdrive", path=f["id"]) for f in files]

def list_github_cvs():
    token = os.getenv("GITHUB_TK")
    repo_name = os.getenv("GITHUB_REPO")
    folder_path = os.getenv("GITHUB_FOLDER", "")
    if not token or not repo_name:
        return []
    g = Github(token)
    repo = g.get_repo(repo_name)
    files = repo.get_contents(folder_path)
    cv_files = []
    for f in files:
        if f.type == 'file' and (f.name.lower().endswith('.pdf') or f.name.lower().endswith('.docx')):
            cv_files.append(CVInfo(name=f.name, source="github", path=f.path))
    return cv_files

def move_to_qualified_folder(file_id: str, qualified_folder_id: str) -> bool:
    """Move the file to the qualified candidates folder in Google Drive."""
    try:
        creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        
        if not creds_json or not qualified_folder_id:
            print("[ERROR] Google Drive credentials or qualified folder ID not set")
            return False
            
        if creds_json.strip().startswith('{'):
            creds_dict = json.loads(creds_json)
        else:
            with open(creds_json) as f:
                creds_dict = json.load(f)
                
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        )
        service = build('drive', 'v3', credentials=creds)
        
        try:
            # Get current file metadata including parents
            file = service.files().get(
                fileId=file_id,
                fields='parents,name'
            ).execute()
            
            # Remove the file from its current folder
            previous_parents = ",".join(file.get('parents', []))
            
            # Move the file to the qualified folder
            updated_file = service.files().update(
                fileId=file_id,
                addParents=qualified_folder_id,
                removeParents=previous_parents,
                fields='id, parents, name'
            ).execute()
            
            print(f"[INFO] Successfully moved file {file.get('name')} to qualified folder")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error accessing file {file_id}: {str(e)}")
            return False
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to move file {file_id} to qualified folder: {str(e)}")
        return False

@app.get("/gdrive/folders")
def get_gdrive_folders(parent_id: Optional[str] = None):
    return list_gdrive_folders(parent_id=parent_id)

@app.get("/cvs", response_model=List[CVInfo])
def list_cvs(source: str = Query(..., regex="^(gdrive|github)$"), folder_id: Optional[str] = None):
    if source == 'gdrive':
        return list_gdrive_cvs(folder_id)
    else:
        return list_github_cvs()

@app.post("/review", response_model=ReviewResult)
def review_cv(cv: CVInfo):
    # Fetch CV content
    if cv.source == 'gdrive':
        cv_text = get_gdrive_cv_content(cv.path)
    elif cv.source == 'github':
        cv_text = get_github_cv_content(cv.path)
    else:
        return ReviewResult(cv_name=cv.name, review="Invalid source.")
    # Run CrewAI + OpenAI review, now with job description
    review = run_openai_review(cv_text, cv.name, cv.job_description)
    if hasattr(review, "raw"):
        review = review.raw
    return ReviewResult(cv_name=cv.name, review=review)

@app.post("/review_all", response_model=List[ReviewAllResult])
async def review_all_cvs(
    cvs: List[CVInfo],
    job_description: Optional[str] = Body(None),
    qualified_folder_id: Optional[str] = Body(None)
):

    # Create a single ThreadPoolExecutor for all tasks
    executor = ThreadPoolExecutor(max_workers=min(32, len(cvs) + 4))
    loop = asyncio.get_event_loop()
    
    async def process_cv(cv):
        try:
            # Step 2: Get CV text
            try:
                cv_text = await loop.run_in_executor(
                    executor,
                    get_gdrive_cv_content if cv.source == 'gdrive' else get_github_cv_content,
                    cv.path
                )
            except Exception as e:
                print(f"[ERROR] Failed to get CV text for {cv.name}: {str(e)}")
                return ReviewAllResult(
                    cv_name=cv.name,
                    review=f"Error getting CV content: {str(e)}",
                    fit_score=0,
                    token_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0
                )

            # Step 3: Run OpenAI/CrewAI review
            try:
                review_output = await loop.run_in_executor(
                    executor,
                    run_openai_review,
                    cv_text,
                    cv.name,
                    job_description
                )
                review = review_output.raw if hasattr(review_output, "raw") else str(review_output)
                # Get token usage from review_output
                token_usage = getattr(review_output, "token_usage", None)
                if token_usage and hasattr(token_usage, "prompt_tokens"):
                    prompt_tokens = token_usage.prompt_tokens
                    completion_tokens = token_usage.completion_tokens
                    total_tokens = token_usage.total_tokens
                else:
                    # Fallback to estimating tokens if exact count not available
                    total_tokens = len(review.split()) * 2  # Rough estimate
                    prompt_tokens = len(cv_text.split())  # Rough estimate for input
                    completion_tokens = total_tokens - prompt_tokens
                token_count = total_tokens
            except Exception as e:
                print(f"[ERROR] Failed to review CV {cv.name}: {str(e)}")
                return ReviewAllResult(
                    cv_name=cv.name,
                    review=f"Error during CV review: {str(e)}",
                    fit_score=0,
                    token_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0
                )

            # Step 4: Extract fit score with improved regex and parsing
            fit_score = extract_fit_score(review)

            # Debug logging
            print(f"[DEBUG] {cv.name} Fit Score: {fit_score}")
            
            # Step 5: Move qualified CVs to the qualified folder
            moved_to_qualified = False
            if fit_score > 80 and cv.source == 'gdrive':
                try:
                    moved_to_qualified = await loop.run_in_executor(
                        executor,
                        move_to_qualified_folder,
                        cv.path,
                        qualified_folder_id
                    )
                    if moved_to_qualified:
                        print(f"[INFO] Moved qualified CV {cv.name} to qualified folder")
                except Exception as e:
                    print(f"[ERROR] Failed to move CV {cv.name} to qualified folder: {str(e)}")
                    # Continue processing even if move fails

            return ReviewAllResult(
                cv_name=cv.name,
                review=f"{review}\n\n{'[Moved to qualified folder]' if moved_to_qualified else ''}",
                fit_score=fit_score,
                token_count=token_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

        except Exception as e:
            # Don't let one error fail all
            print(f"[ERROR] Failed to process CV '{cv.name}': {e}")
            return ReviewAllResult(
                cv_name=cv.name,
                review=f"[Error processing CV: {str(e)}]",
                fit_score=0
            )
            
    if not cvs:
        return []

    try:
        # Process all CVs in parallel
        tasks = [process_cv(cv) for cv in cvs]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out any exceptions and convert them to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"[ERROR] Task for CV {cvs[i].name} failed: {str(result)}")
                    processed_results.append(ReviewAllResult(
                        cv_name=cvs[i].name,
                        review=f"Error processing CV: {str(result)}",
                        fit_score=0
                    ))
                else:
                    processed_results.append(result)

            # Sort results by fit score (descending)
            sorted_results = sorted(processed_results, key=lambda x: x.fit_score, reverse=True)
            return sorted_results
        except Exception as e:
            print(f"[ERROR] Failed to gather results: {str(e)}")
            return [ReviewAllResult(
                cv_name="System Error",
                review=f"Failed to process CVs: {str(e)}",
                fit_score=0
            )]
    finally:
        # Ensure the executor is shut down properly
        try:
            executor.shutdown(wait=True)
        except Exception as e:
            print(f"[ERROR] Failed to shutdown executor: {str(e)}")



@app.get("/job_description", response_class=PlainTextResponse)
def get_job_description(folder_id: Optional[str] = None):
    """Endpoint to get the job description from Google Drive."""
    return get_job_description_from_drive(folder_id)

@app.get("/cv_content", response_class=PlainTextResponse)
def get_cv_content(source: str, path: str):
    if source == 'gdrive':
        return get_gdrive_cv_content(path)
    elif source == 'github':
        return get_github_cv_content(path)
    return "Invalid source"

# Webhook endpoints for automatic CV processing
@app.post("/webhook/drive")
async def handle_drive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Google Drive push notifications for automatic CV processing."""
    return await webhook_handler.handle_drive_notification(request, background_tasks)

@app.post("/webhook/setup")
async def setup_webhook_monitoring(
    folder_id: str = Body(...),
    position_name: str = Body(...)
):
    """Setup webhook monitoring for a specific Google Drive folder."""
    try:
        result = await webhook_handler.setup_webhook_for_folder(folder_id, position_name)
        return {"status": "success", "channel_info": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/stop")
async def stop_webhook_monitoring(channel_id: str = Body(...)):
    """Stop webhook monitoring for a specific channel."""
    try:
        await webhook_handler.stop_webhook_for_folder(channel_id)
        return {"status": "success", "message": f"Stopped monitoring channel {channel_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/webhook/status")
def get_webhook_status():
    """Get current webhook monitoring status."""
    return {
        "monitored_folders": webhook_handler.monitored_folders,
        "active_channels": list(webhook_handler.webhook_channels.keys())
    }

# Auto-processing endpoints (polling-based alternative)
@app.post("/auto-process/start")
async def start_auto_processing():
    """Start automatic CV processing using polling method."""
    try:
        await auto_processor.start_monitoring()
        return {"status": "success", "message": "Auto-processing started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auto-process/stop")
def stop_auto_processing():
    """Stop automatic CV processing."""
    auto_processor.stop_monitoring()
    return {"status": "success", "message": "Auto-processing stopped"}

@app.post("/auto-process/add-folder")
async def add_folder_to_auto_process(
    folder_id: str = Body(...),
    position_name: str = Body(...)
):
    """Add a folder to automatic processing monitoring."""
    try:
        await auto_processor.add_folder_to_monitor(folder_id, position_name)
        return {"status": "success", "message": f"Added {position_name} to auto-processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auto-process/remove-folder")
def remove_folder_from_auto_process(folder_id: str = Body(...)):
    """Remove a folder from automatic processing monitoring."""
    auto_processor.remove_folder_from_monitor(folder_id)
    return {"status": "success", "message": "Folder removed from auto-processing"}

@app.get("/auto-process/status")
def get_auto_process_status():
    """Get current auto-processing status."""
    return auto_processor.get_status() 