import os
from fastapi import FastAPI, Query, Body
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
    job_description: Optional[str] = None

# Placeholder for review result
class ReviewResult(BaseModel):
    cv_name: str
    review: str

class ReviewAllResult(BaseModel):
    cv_name: str
    review: str
    fit_score: int

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

def run_gemini_review(cv_text, cv_name, job_description=None):
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
    description = f"Review the following CV named {cv_name} for skills, experience, and formatting."
    if job_description:
        description += f"\n\nMatch the CV to the following job description and provide feedback on fit:\n{job_description}"
    # Ask for a numeric fit score in the output
    description += ("\n\nCV Content:\n" + cv_text +
        "\n\nIn your response, provide a numeric fit score (0-100) for how well this CV matches the job description, "
        "and then provide a structured, actionable review. Format your response as follows:\n"
        "Fit Score: <number>\nReview: <your review text>")
    task = Task(
        description=description,
        agent=agent,
        expected_output="A structured, actionable review of the CV, including feedback on skills, experience, formatting, and fit for the job description if provided. Include a numeric fit score (0-100) at the top of your response."
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
    # Run CrewAI + Gemini review, now with job description
    review = run_gemini_review(cv_text, cv.name, cv.job_description)
    if hasattr(review, "raw"):
        review = review.raw
    return ReviewResult(cv_name=cv.name, review=review)

@app.post("/review_all", response_model=List[ReviewAllResult])
def review_all_cvs(
    source: str = Query(..., regex="^(gdrive|github)$"),
    job_description: Optional[str] = Body(None)
):
    # Step 1: List all CVs based on source
    cvs = list_gdrive_cvs() if source == 'gdrive' else list_github_cvs()
    results = []

    for cv in cvs:
        try:
            # Step 2: Get CV text
            cv_text = (
                get_gdrive_cv_content(cv.path)
                if cv.source == 'gdrive'
                else get_github_cv_content(cv.path)
            )

            # Step 3: Run Gemini/CrewAI review
            review_output = run_gemini_review(cv_text, cv.name, job_description)
            review = review_output.raw if hasattr(review_output, "raw") else str(review_output)

            # Step 4: Extract fit score with improved regex and parsing
            fit_score = extract_fit_score(review)

            # Debug logging
            print(f"[DEBUG] {cv.name} Fit Score: {fit_score}")

            # Step 5: Append result
            results.append(ReviewAllResult(
                cv_name=cv.name,
                review=review,
                fit_score=fit_score
            ))

        except Exception as e:
            # Don't let one error fail all
            print(f"[ERROR] Failed to process CV '{cv.name}': {e}")
            results.append(ReviewAllResult(
                cv_name=cv.name,
                review=f"[Error processing CV: {str(e)}]",
                fit_score=0
            ))

    # Step 6: Sort by fit score (descending)
    results.sort(key=lambda x: x.fit_score, reverse=True)
    return results


def extract_fit_score(review_text: str) -> int:
    """
    Extract fit score from review text with multiple fallback patterns.
    Returns an integer between 0-100, defaulting to 0 if not found.
    """
    if not review_text:
        return 0
    
    # Multiple regex patterns to catch different formats
    patterns = [
        # "Fit Score: 85" or "fit score: 85" (case insensitive, at start of line)
        r"(?i)^fit\s*score\s*:\s*(\d+(?:\.\d+)?)",
        
        # "Fit Score: 85" anywhere in text
        r"(?i)fit\s*score\s*:\s*(\d+(?:\.\d+)?)",
        
        # "Score: 85" or "Overall Score: 85"
        r"(?i)(?:overall\s+)?score\s*:\s*(\d+(?:\.\d+)?)",
        
        # "85/100" or "85 out of 100"
        r"(\d+(?:\.\d+)?)\s*(?:/100|out\s+of\s+100)",
        
        # Numbers followed by % (assuming it's out of 100)
        r"(\d+(?:\.\d+)?)%",
        
        # Just look for any number in parentheses like "(85)"
        r"\((\d+(?:\.\d+)?)\)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, review_text, re.MULTILINE)
        if matches:
            try:
                # Take the first match
                score = float(matches[0])
                
                # Ensure score is within reasonable bounds (0-100)
                if score > 100:
                    score = min(score, 100)  # Cap at 100
                elif score < 0:
                    score = 0
                
                return int(round(score))
            except (ValueError, TypeError) as e:
                print(f"[WARN] Failed to parse score '{matches[0]}': {e}")
                continue
    
    # If no patterns match, try to find any number that might be a score
    # Look for standalone numbers between 0-100
    standalone_numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', review_text)
    for num_str in standalone_numbers:
        try:
            num = float(num_str)
            if 0 <= num <= 100:
                print(f"[INFO] Using standalone number {num} as potential fit score")
                return int(round(num))
        except ValueError:
            continue
    
    print(f"[WARN] No fit score found in review text: {review_text[:200]}...")
    return 0


@app.get("/cv_content", response_class=PlainTextResponse)
def get_cv_content(source: str, path: str):
    if source == 'gdrive':
        return get_gdrive_cv_content(path)
    elif source == 'github':
        return get_github_cv_content(path)
    return "Invalid source" 