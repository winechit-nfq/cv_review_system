# Automatic CV Processing Setup Guide

This guide explains how to set up automatic CV processing so that when CVs are uploaded to Google Drive, they are automatically reviewed without clicking the review button.

## Overview

There are two approaches to automatic CV processing:

1. **Webhooks (Recommended)** - Real-time notifications from Google Drive
2. **Polling** - Periodically check for new files

## Option 1: Webhook-Based Auto-Processing (Recommended)

### How It Works

1. Google Drive sends push notifications to your application when files are uploaded
2. Your application receives the notification immediately
3. New CV files are automatically processed by AI agents
4. Qualified candidates (score > 80%) are moved to the "qualified_cv_list" folder

### Prerequisites

- Your backend must be publicly accessible (use ngrok for local development)
- Google Drive API credentials with proper permissions
- Proper folder structure in Google Drive

### Quick Setup for Local Development

1. **Install ngrok** (if not already installed):
   ```bash
   # macOS
   brew install ngrok
   
   # Linux
   sudo snap install ngrok
   
   # Windows - download from https://ngrok.com/download
   ```

2. **Authenticate ngrok**:
   ```bash
   ngrok authtoken YOUR_AUTHTOKEN
   ```
   Get your token from: https://dashboard.ngrok.com/get-started/your-authtoken

3. **Run the automated setup**:
   ```bash
   ./setup-webhooks.sh local
   ```

   This script will:
   - Start your FastAPI server
   - Create an ngrok tunnel
   - Update your .env file with the webhook URL
   - Provide instructions for next steps

4. **Configure monitoring**:
   - Open http://localhost:3000/webhook-setup.html
   - Select positions you want to auto-monitor
   - Click "Enable Auto-Processing"

### Manual Setup

1. **Update .env file**:
   ```bash
   WEBHOOK_BASE_URL=https://your-public-domain.com
   ```

2. **Deploy your backend** to a publicly accessible server (Heroku, Railway, etc.)

3. **Test webhook endpoint**:
   ```bash
   curl https://your-domain.com/webhook/status
   ```

4. **Configure monitoring** via the web interface

### Production Deployment

1. **Deploy to cloud platform**:
   ```bash
   # Example with Heroku
   heroku create your-cv-review-app
   git push heroku main
   
   # Set environment variables
   heroku config:set WEBHOOK_BASE_URL=https://your-cv-review-app.herokuapp.com
   heroku config:set OPENAI_API_KEY=your_key
   # ... other env vars
   ```

2. **Configure webhook monitoring**:
   - Visit https://your-app.herokuapp.com/webhook-setup.html
   - Setup monitoring for desired positions

## Option 2: Polling-Based Auto-Processing (Simpler Alternative)

### How It Works

1. The application periodically checks monitored folders (every 5 minutes)
2. New CV files are detected and processed automatically
3. No external webhooks required - works entirely within your application

### Setup

1. **Start auto-processing**:
   ```bash
   curl -X POST http://localhost:8000/auto-process/start
   ```

2. **Add folders to monitor**:
   ```bash
   curl -X POST http://localhost:8000/auto-process/add-folder \
     -H "Content-Type: application/json" \
     -d '{"folder_id": "your_cv_folder_id", "position_name": "Senior Developer"}'
   ```

3. **Check status**:
   ```bash
   curl http://localhost:8000/auto-process/status
   ```

### Advantages of Polling
- Simpler to set up (no external URLs needed)
- Works behind firewalls
- No webhook management required

### Disadvantages of Polling
- Slight delay (up to 5 minutes) before processing
- More resource intensive
- Less real-time than webhooks

## Google Drive Folder Structure

Your Google Drive should be organized like this:

```
Position Folders/
├── Senior Frontend Developer/
│   ├── cv_list/                 <- CVs uploaded here
│   ├── job_description/         <- Job description files
│   └── qualified_cv_list/       <- Qualified CVs moved here automatically
├── Backend Developer/
│   ├── cv_list/
│   ├── job_description/
│   └── qualified_cv_list/
└── DevOps Engineer/
    ├── cv_list/
    ├── job_description/
    └── qualified_cv_list/
```

## Environment Variables

Add these to your `.env` file:

```bash
# Required for webhooks
WEBHOOK_BASE_URL=https://your-domain.com

# Existing variables (keep these)
OPENAI_API_KEY=your_openai_api_key
GOOGLE_DRIVE_CREDENTIALS=path_to_credentials.json
GOOGLE_DRIVE_FOLDER_ID=your_root_folder_id
```

## API Endpoints

### Webhook Endpoints
- `POST /webhook/drive` - Receive Google Drive notifications
- `POST /webhook/setup` - Setup monitoring for a folder
- `POST /webhook/stop` - Stop monitoring a channel
- `GET /webhook/status` - Get webhook status

### Auto-Processing Endpoints (Polling)
- `POST /auto-process/start` - Start polling-based monitoring
- `POST /auto-process/stop` - Stop auto-processing
- `POST /auto-process/add-folder` - Add folder to monitor
- `POST /auto-process/remove-folder` - Remove folder from monitoring
- `GET /auto-process/status` - Get auto-processing status

## Testing Auto-Processing

1. **Setup monitoring** for a test position
2. **Upload a CV** to the monitored folder
3. **Check logs** for processing messages
4. **Verify** that qualified CVs are moved to the qualified folder

## Troubleshooting

### Webhooks Not Working
- Check if WEBHOOK_BASE_URL is publicly accessible
- Verify Google Drive API permissions
- Check server logs for webhook errors
- Ensure proper folder structure

### Polling Not Detecting Files
- Check if auto-processing is started
- Verify folder IDs are correct
- Check Google Drive API credentials
- Look at application logs

### CVs Not Being Processed
- Verify file formats (PDF/DOCX only)
- Check job description availability
- Verify OpenAI API key is working
- Check application logs for errors

## Performance Considerations

### Webhooks
- Real-time processing
- Minimal resource usage
- Requires public endpoint

### Polling
- 5-minute processing delay
- Higher API usage
- Works behind firewalls

## Security Notes

- Keep your webhook endpoint secure
- Use HTTPS in production
- Validate webhook signatures (if needed)
- Monitor API usage and costs
- Protect your Google Drive credentials

## Support

If you encounter issues:

1. Check the application logs
2. Verify your Google Drive folder structure
3. Test your API endpoints manually
4. Ensure all environment variables are set
5. Check Google Drive API quotas

For webhook-specific issues, see Google Drive API documentation:
https://developers.google.com/drive/api/v3/push
