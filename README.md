# CV Review System for HR

This system allows HR to review CVs using CrewAI with Gemini API, reading CVs from Google Drive or GitHub.

## Setup

1. Clone the repository and navigate to the project directory.
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your API keys:
   - `GEMINI_API_KEY`: Your Gemini API key
   - `GOOGLE_DRIVE_CREDENTIALS`: Google Drive credentials (JSON string or path)
   - `GOOGLE_DRIVE_FOLDER_ID`: Google Drive folder ID containing CVs
   - `GITHUB_TOKEN`: GitHub personal access token
   - `GITHUB_REPO`: GitHub repo in `owner/repo` format
   - `GITHUB_FOLDER`: (Optional) Path to folder in repo containing CVs

## Running the Backend

```bash
uvicorn backend.main:app --reload
```

## API Endpoints
- `GET /cvs?source=gdrive|github` — List CVs from Google Drive or GitHub
- `POST /review` — Review a selected CV

## Frontend
A simple web UI will be provided for HR to interact with the system. 

---

## 1. **Set Up Environment Variables**

Create a `.env` file in your project root (or copy from `.env.example`) and fill in:

```env
GEMINI_API_KEY=your_gemini_api_key_here

GOOGLE_DRIVE_CREDENTIALS=your_google_drive_credentials_here
GOOGLE_DRIVE_FOLDER_ID=your_gdrive_folder_id_here

GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=your_github_owner/your_repo_name
GITHUB_FOLDER=path/to/cv/folder  # optional
```

---

## 2. **Activate the Virtual Environment**

```bash
source venv/bin/activate
```

---

## 3. **Install All Requirements**

```bash
pip install -r requirements.txt
```

If you see errors about missing packages (like `googleapiclient`), also run:

```bash
pip install google-api-python-client
```

---

## 4. **Run the Backend Server**

```bash
uvicorn backend.main:app --reload
```

- The server will run at: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 5. **Open the Frontend**

Open `frontend/index.html` in your browser (double-click or use `open frontend/index.html` on Mac).

---

## 6. **Usage**

- Select the source (Google Drive or GitHub).
- Click “Load CVs” to see the list.
- Use “Preview” to see the CV content.
- Use “Review” to get an AI-generated review.

---

**If you see errors about missing modules, make sure you’re in the virtual environment and all dependencies are installed.**

If you need help with any step or see an error, let me know the details! 