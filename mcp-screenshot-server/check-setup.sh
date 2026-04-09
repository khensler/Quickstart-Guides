#!/bin/bash

# MCP Screenshot Server - Setup Checker
# This script verifies that all prerequisites are installed

echo "🔍 MCP Screenshot Server - Setup Checker"
echo "=========================================="
echo ""

# Check Node.js
echo "Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js is installed: $NODE_VERSION"
    
    # Check version is >= 18
    MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$MAJOR_VERSION" -ge 18 ]; then
        echo "   Version is compatible (>= 18)"
    else
        echo "⚠️  Warning: Node.js version should be 18 or higher"
    fi
else
    echo "❌ Node.js is NOT installed"
    echo "   Install from: https://nodejs.org/"
    echo "   Or use: brew install node (macOS)"
fi
echo ""

# Check npm
echo "Checking npm..."
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "✅ npm is installed: v$NPM_VERSION"
else
    echo "❌ npm is NOT installed (should come with Node.js)"
fi
echo ""

# Check if we're in the right directory
echo "Checking project structure..."
if [ -f "package.json" ]; then
    echo "✅ package.json found"
else
    echo "❌ package.json not found - are you in the mcp-screenshot-server directory?"
fi

if [ -f "tsconfig.json" ]; then
    echo "✅ tsconfig.json found"
else
    echo "❌ tsconfig.json not found"
fi
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
if [ -d "node_modules" ]; then
    echo "✅ node_modules directory exists"
    
    if [ -d "node_modules/@modelcontextprotocol" ]; then
        echo "✅ MCP SDK is installed"
    else
        echo "⚠️  MCP SDK not found - run: npm install"
    fi
    
    if [ -d "node_modules/playwright" ]; then
        echo "✅ Playwright is installed"
    else
        echo "⚠️  Playwright not found - run: npm install"
    fi
else
    echo "❌ node_modules not found - run: npm install"
fi
echo ""

# Check if built
echo "Checking build..."
if [ -d "dist" ]; then
    echo "✅ dist directory exists"
    
    if [ -f "dist/index.js" ]; then
        echo "✅ Server is built (dist/index.js exists)"
    else
        echo "⚠️  Server not built - run: npm run build"
    fi
else
    echo "❌ dist directory not found - run: npm run build"
fi
echo ""

# Check Playwright browsers
echo "Checking Playwright browsers..."
if command -v npx &> /dev/null; then
    # Try to check if browsers are installed
    if [ -d "$HOME/Library/Caches/ms-playwright" ] || [ -d "$HOME/.cache/ms-playwright" ]; then
        echo "✅ Playwright browsers appear to be installed"
    else
        echo "⚠️  Playwright browsers may not be installed"
        echo "   Run: npx playwright install chromium"
    fi
else
    echo "⚠️  Cannot check Playwright browsers (npx not found)"
fi
echo ""

# Check screenshots directory
echo "Checking screenshots directory..."
if [ -d "screenshots" ]; then
    echo "✅ screenshots directory exists"
else
    echo "ℹ️  screenshots directory will be created automatically"
fi
echo ""

# Summary
echo "=========================================="
echo "📋 Summary"
echo "=========================================="
echo ""

if command -v node &> /dev/null && [ -f "dist/index.js" ]; then
    echo "✅ Server appears ready to use!"
    echo ""
    echo "Next steps:"
    echo "1. Get the absolute path: pwd"
    echo "2. Add to Claude Desktop config:"
    echo "   {\"mcpServers\": {\"screenshot\": {\"command\": \"node\", \"args\": [\"$(pwd)/dist/index.js\"]}}}"
    echo "3. Restart Claude Desktop"
else
    echo "⚠️  Setup incomplete. Please:"
    if ! command -v node &> /dev/null; then
        echo "   1. Install Node.js from https://nodejs.org/"
    fi
    if [ ! -d "node_modules" ]; then
        echo "   2. Run: npm install"
    fi
    if [ ! -d "dist" ]; then
        echo "   3. Run: npm run build"
    fi
    echo "   4. Run: npx playwright install chromium"
fi
echo ""

