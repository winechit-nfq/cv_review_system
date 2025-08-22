#!/bin/bash

# CV Review System - Webhook Setup Script
# This script helps you set up automatic CV processing with Google Drive webhooks

echo "🚀 CV Review System - Webhook Setup"
echo "====================================="
echo ""

# Check if running locally
if [[ "$1" == "local" ]]; then
    echo "🏠 Setting up for LOCAL DEVELOPMENT with ngrok"
    echo ""
    
    # Check if ngrok is installed
    if ! command -v ngrok &> /dev/null; then
        echo "❌ ngrok is not installed. Please install it first:"
        echo "   macOS: brew install ngrok"
        echo "   Linux: snap install ngrok"
        echo "   Windows: Download from https://ngrok.com/download"
        exit 1
    fi
    
    # Check if ngrok is authenticated
    if [ ! -f ~/.ngrok2/ngrok.yml ]; then
        echo "❌ ngrok is not authenticated. Please run:"
        echo "   ngrok authtoken YOUR_AUTHTOKEN"
        echo "   Get your token from: https://dashboard.ngrok.com/get-started/your-authtoken"
        exit 1
    fi
    
    echo "✅ ngrok is installed and authenticated"
    echo ""
    
    # Start the FastAPI server in background
    echo "🔧 Starting FastAPI server..."
    cd backend
    python -m uvicorn main:app --reload --port 8000 &
    SERVER_PID=$!
    cd ..
    
    # Wait for server to start
    echo "⏳ Waiting for server to start..."
    sleep 5
    
    # Start ngrok tunnel
    echo "🌐 Starting ngrok tunnel..."
    ngrok http 8000 --log=stdout > ngrok.log &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 3
    
    # Get ngrok URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['tunnels'][0]['public_url'])
except:
    print('')
")
    
    if [ -z "$NGROK_URL" ]; then
        echo "❌ Failed to get ngrok URL. Please check ngrok.log"
        kill $SERVER_PID $NGROK_PID 2>/dev/null
        exit 1
    fi
    
    echo "✅ ngrok tunnel established: $NGROK_URL"
    echo ""
    
    # Update .env file
    echo "📝 Updating .env file with webhook URL..."
    
    if grep -q "WEBHOOK_BASE_URL=" .env; then
        # Update existing line
        sed -i '' "s|WEBHOOK_BASE_URL=.*|WEBHOOK_BASE_URL=$NGROK_URL|" .env
    else
        # Add new line
        echo "WEBHOOK_BASE_URL=$NGROK_URL" >> .env
    fi
    
    echo "✅ Updated WEBHOOK_BASE_URL in .env file"
    echo ""
    
    echo "🎉 Setup complete! Your webhook endpoint is:"
    echo "   $NGROK_URL/webhook/drive"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Open http://localhost:3000/webhook-setup.html to configure monitoring"
    echo "   2. Select positions you want to auto-monitor"
    echo "   3. Upload CVs to monitored folders to test automatic processing"
    echo ""
    echo "⚠️  Important: Keep this terminal open to maintain the ngrok tunnel"
    echo "    Press Ctrl+C to stop the webhook service"
    echo ""
    
    # Wait for user to stop
    trap "echo ''; echo '🛑 Stopping services...'; kill $SERVER_PID $NGROK_PID 2>/dev/null; echo '✅ Stopped'; exit 0" INT
    
    # Keep running
    wait
    
else
    echo "🌍 Setting up for PRODUCTION DEPLOYMENT"
    echo ""
    echo "📋 Production setup checklist:"
    echo ""
    echo "1. ✅ Deploy your FastAPI backend to a cloud service:"
    echo "   - Heroku: heroku create your-app-name"
    echo "   - Railway: railway deploy"
    echo "   - DigitalOcean App Platform"
    echo "   - AWS/GCP/Azure"
    echo ""
    echo "2. ✅ Set the WEBHOOK_BASE_URL environment variable:"
    echo "   - Example: WEBHOOK_BASE_URL=https://your-app.herokuapp.com"
    echo ""
    echo "3. ✅ Ensure your deployment includes all dependencies:"
    echo "   - pip install -r requirements.txt"
    echo ""
    echo "4. ✅ Configure Google Drive API credentials in production"
    echo ""
    echo "5. ✅ Test webhook endpoint:"
    echo "   - GET https://your-app.com/webhook/status"
    echo ""
    echo "6. ✅ Open your frontend and configure monitoring:"
    echo "   - https://your-app.com/webhook-setup.html"
    echo ""
    
    # Check current WEBHOOK_BASE_URL
    if grep -q "WEBHOOK_BASE_URL=" .env; then
        CURRENT_URL=$(grep "WEBHOOK_BASE_URL=" .env | cut -d'=' -f2)
        echo "📍 Current WEBHOOK_BASE_URL: $CURRENT_URL"
        echo ""
        
        if [[ "$CURRENT_URL" == "https://your-domain.com" ]]; then
            echo "⚠️  Please update WEBHOOK_BASE_URL in .env with your actual domain"
        fi
    else
        echo "⚠️  WEBHOOK_BASE_URL not set in .env file"
    fi
fi

echo ""
echo "📚 For more information, see:"
echo "   - Google Drive API Push Notifications: https://developers.google.com/drive/api/v3/push"
echo "   - Webhook troubleshooting guide in README.md"
