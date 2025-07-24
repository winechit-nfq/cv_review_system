import os
from fastapi import FastAPI, Query
from typing import List, Optional
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
from google.oauth2 import service_account
from github import Github
from fastapi.responses import PlainTextResponse
import base64
from crewai import Crew, Agent, Task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Placeholder for CV metadata
class CVInfo(BaseModel):
    name: str
    source: str  # 'gdrive' or 'github'
    path: str

# Placeholder for review result
class ReviewResult(BaseModel):
    cv_name: str
    review: str

def list_gdrive_cvs():
    creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not creds_json or not folder_id:
        return []
    import json
    if creds_json.strip().startswith('{'):
        creds_dict = json.loads(creds_json)
    else:
        with open(creds_json) as f:
            creds_dict = json.load(f)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(
        q=f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed=false",
        fields="files(id, name)",
        pageSize=50
    ).execute()
    files = results.get('files', [])
    return [CVInfo(name=f["name"], source="gdrive", path=f["id"]) for f in files]

def list_github_cvs():
    token = os.getenv("GITHUB_TOKEN")
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

def get_gdrive_cv_content(file_id):
    creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
    import json
    if creds_json.strip().startswith('{'):
        creds_dict = json.loads(creds_json)
    else:
        with open(creds_json) as f:
            creds_dict = json.load(f)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    service = build('drive', 'v3', credentials=creds)
    file = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime = file['mimeType']
    if mime == 'application/pdf':
        data = service.files().get_media(fileId=file_id).execute()
        import io
        from pdfminer.high_level import extract_text
        text = extract_text(io.BytesIO(data))
        return text
    elif mime == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        data = service.files().get_media(fileId=file_id).execute()
        import io
        from docx import Document
        doc = Document(io.BytesIO(data))
        return '\n'.join([p.text for p in doc.paragraphs])
    return "Unsupported file type"

def get_github_cv_content(path):
    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPO")
    if not token or not repo_name:
        return ""
    g = Github(token)
    repo = g.get_repo(repo_name)
    file_content = repo.get_contents(path)
    if file_content.name.lower().endswith('.pdf'):
        import io
        from pdfminer.high_level import extract_text
        data = base64.b64decode(file_content.content)
        text = extract_text(io.BytesIO(data))
        return text
    elif file_content.name.lower().endswith('.docx'):
        import io
        from docx import Document
        data = base64.b64decode(file_content.content)
        doc = Document(io.BytesIO(data))
        return '\n'.join([p.text for p in doc.paragraphs])
    return "Unsupported file type"

def run_gemini_review(cv_text, cv_name):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return "Gemini API key not set."
    # Setup CrewAI agent with Gemini
    
    agent = Agent(
        name="CV Reviewer",
        role="HR Expert",  # Add a role
        goal="Review CVs for skills, experience, and formatting",  # Add a goal
        backstory="An experienced HR professional who provides actionable feedback on CVs.",  # Add a backstory
    )
    task = Task(
        description="Review the following CV named {cv_name} for skills, experience, and formatting. Provide structured feedback.\n\nCV Content:\n{cv_text}",
        agent=agent,
        expected_output="A structured, actionable review of the CV, including feedback on skills, experience, and formatting."
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
    )
    
    result = crew.kickoff()
    return result

@app.get("/cvs", response_model=List[CVInfo])
def list_cvs(source: str = Query(..., regex="^(gdrive|github)$")):
    if source == 'gdrive':
        return list_gdrive_cvs()
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
    # Run CrewAI + Gemini review
    review = run_gemini_review(cv_text, cv.name)
    # Extract string if needed
    if hasattr(review, "raw"):
        review = review.raw
    return ReviewResult(cv_name=cv.name, review=review)

@app.get("/cv_content", response_class=PlainTextResponse)
def get_cv_content(source: str, path: str):
    if source == 'gdrive':
        return get_gdrive_cv_content(path)
    elif source == 'github':
        return get_github_cv_content(path)
    return "Invalid source" 