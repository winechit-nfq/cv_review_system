
# 🤖 CV Review System

An intelligent CV analysis platform that revolutionizes HR recruitment. Powered by Google's Gemini API, it provides automated CV review, smart candidate ranking, and seamless integration with popular document sources.

## ✨ Key Features

- 🔄 **Smart CV Management**
  - Import from Google Drive or GitHub
  - Support for PDF and DOCX formats
  - Bulk CV processing
  
- 🤖 **AI-Powered Analysis**
  - Advanced CV parsing and understanding
  - Skill matching with job requirements
  - Experience level assessment
  - Education qualification analysis
  
- 📊 **Intelligent Ranking**
  - Customizable scoring system
  - Automated candidate ranking
  - Comparative analysis
  - Detailed match percentages
  
- 🎯 **Job Matching**
  - Real-time requirement matching
  - Skills gap analysis
  - Cultural fit assessment
  - Experience relevance scoring
  
- 👀 **Enhanced User Experience**
  - Instant CV preview
  - Dark/Light mode
  - Responsive design
  - Keyboard shortcuts
  
- 📈 **Reporting & Analytics**
  - Exportable results (CSV, PDF)
  - Batch processing statistics
  - Candidate comparison charts
  - Historical data tracking

## � System Requirements

### Minimum Requirements
- CPU: Dual-core processor
- RAM: 4GB
- Storage: 500MB free space
- Internet: Stable connection (1Mbps+)

### Recommended Setup
- CPU: Quad-core processor
- RAM: 8GB
- Storage: 1GB free space
- Internet: 5Mbps+ connection

### Software Prerequisites
- Python 3.8 or higher
- Modern web browser (Chrome 90+, Firefox 90+, Safari 15+)
- Google Cloud account (for API access)
- GitHub account (optional)

## 🚀 Installation Guide

### 1. Project Setup

```bash
# Clone the repository
git clone https://github.com/winechit-nfq/cv_review_system.git
cd cv_review_system

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows (CMD):
venv\Scripts\activate.bat

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
```

### 2. Dependencies Installation

```bash
# Update pip to latest version
python -m pip install --upgrade pip

# Install core dependencies
pip install -r requirements.txt

# Install additional Google API packages
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Install optional utilities (recommended)
pip install rich  # for better terminal output
pip install python-dotenv  # for environment management
```

### 3. Configure Your Environment

1. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

2. Add your credentials:
   ```env
   # Required: Gemini API credentials
   GEMINI_API_KEY=your_gemini_api_key

   # For Google Drive integration
   GOOGLE_DRIVE_CREDENTIALS=path/to/credentials.json  # or JSON string
   GOOGLE_DRIVE_FOLDER_ID=your_folder_id

   # For GitHub integration (optional)
   GITHUB_TOKEN=your_personal_access_token
   GITHUB_REPO=username/repository
   GITHUB_FOLDER=path/to/cv/folder  # optional
   ```

## 🖥️ Application Launch Guide

### 1. Start Backend Server

```bash
# Ensure you're in the project root and virtual environment is activated
cd cv_review_system
source venv/bin/activate

# Start the FastAPI backend server
uvicorn backend.main:app --reload --port 8000 --host 0.0.0.0
```

The backend API will be available at:
- Local: http://127.0.0.1:8000
- Network: http://your-ip:8000

### 2. Launch Frontend Interface

Option 1: Development Server (Recommended)
```bash
# Ensure virtual environment is activated
source /Users/nfqlocal/cv_review_system/venv/bin/activate

# Navigate to frontend directory and start server
cd frontend
python -m http.server 8080
```

Access the application at:
- Local: http://localhost:8080
- Network: http://your-ip:8080

Option 2: Static File Access
- **macOS/Linux**: 
  ```bash
  open frontend/index.html
  ```
- **Windows**: 
  ```bash
  start frontend/index.html
  ```
- **Alternative**: Use any static file server (nginx, Apache, etc.)


## 🔗 API Reference

### Core Endpoints

- `GET /cvs`
  - **Query**: `?source=gdrive|github`
  - **Response**: List of available CVs

- `POST /review`
  - **Body**: CV info and job description
  - **Response**: Detailed AI analysis

### Getting Help

- Check the [Issues](https://github.com/winechit-nfq/cv_review_system/issues) section
- Join our community discussions
- Contact support team

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with CrewAI and Gemini API
- Frontend uses modern web technologies
- Special thanks to all contributors