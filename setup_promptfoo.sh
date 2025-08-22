#!/bin/bash

# Promptfoo Setup Script for CV Review System
echo "🚀 Setting up Promptfoo for CV Review System..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js found: $(node --version)"

# Install Promptfoo globally
echo "📦 Installing Promptfoo..."
npm install -g promptfoo

# Verify installation
if command -v promptfoo &> /dev/null; then
    echo "✅ Promptfoo installed successfully: $(promptfoo --version)"
else
    echo "❌ Promptfoo installation failed"
    exit 1
fi

# Create evaluation directories if they don't exist
echo "📁 Creating evaluation directories..."
mkdir -p evaluations/results
mkdir -p evaluations/cache

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install promptfoo pyyaml

# Set up environment variables template
echo "📝 Creating environment template..."
cat > .env.promptfoo << EOF
# Promptfoo Configuration for CV Review System
OPENAI_API_KEY=your_openai_api_key_here
PROMPTFOO_CACHE_PATH=./evaluations/cache
PROMPTFOO_CONFIG_PATH=./evaluations/promptfooconfig.yaml

# Optional: Other LLM providers
# ANTHROPIC_API_KEY=your_anthropic_key
# COHERE_API_KEY=your_cohere_key
EOF

echo "🎯 Running initial configuration check..."
cd evaluations

# Initialize Promptfoo config if needed
if [ ! -f "promptfooconfig.yaml" ]; then
    echo "⚠️  promptfooconfig.yaml not found in evaluations directory"
else
    echo "✅ Found promptfooconfig.yaml"
fi

echo ""
echo "🎉 Promptfoo setup complete!"
echo ""
echo "Next steps:"
echo "1. Set your OPENAI_API_KEY in .env.promptfoo or as environment variable"
echo "2. Run evaluation tests with: promptfoo eval -c evaluations/promptfooconfig.yaml"
echo "3. View results with: promptfoo view"
echo "4. Use the new evaluation endpoints in your FastAPI app:"
echo "   - POST /evaluate/cv_analysis - Full evaluation"
echo "   - POST /evaluate/bias_check - Bias detection only"
echo "   - POST /evaluate/security_check - Security validation"
echo "   - GET /evaluate/health - Health check"
echo ""
echo "📚 Documentation: https://promptfoo.dev/docs/"
