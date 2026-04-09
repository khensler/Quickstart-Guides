# Installation Guide

Complete installation guide for the MCP Screenshot Server.

## Prerequisites

### 1. Install Node.js

The MCP Screenshot Server requires Node.js 18 or later.

#### macOS

**Option A: Using Homebrew (Recommended)**
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Node.js
brew install node

# Verify installation
node --version
npm --version
```

**Option B: Using Official Installer**
1. Download from https://nodejs.org/
2. Choose the LTS version
3. Run the installer
4. Verify: `node --version`

#### Linux

**Ubuntu/Debian:**
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**RHEL/CentOS/Fedora:**
```bash
curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
sudo dnf install -y nodejs
```

**Arch Linux:**
```bash
sudo pacman -S nodejs npm
```

#### Windows

1. Download from https://nodejs.org/
2. Run the installer (includes npm)
3. Restart your terminal
4. Verify: `node --version`

### 2. Verify Node.js Installation

```bash
node --version  # Should show v18.x.x or higher
npm --version   # Should show 9.x.x or higher
```

## Server Installation

### Step 1: Navigate to the Server Directory

```bash
cd /path/to/mcp-screenshot-server
```

### Step 2: Install Dependencies

```bash
npm install
```

This will install:
- `@modelcontextprotocol/sdk` - MCP protocol implementation
- `playwright` - Browser automation library
- TypeScript and type definitions

### Step 3: Install Playwright Browsers

```bash
# Install Chromium (required)
npx playwright install chromium

# Optional: Install additional browsers
npx playwright install firefox
npx playwright install webkit

# Or install all browsers at once
npx playwright install
```

**Note**: Playwright will download browser binaries (~300MB per browser). This is normal and required for screenshot functionality.

### Step 4: Build the Server

```bash
npm run build
```

This compiles TypeScript to JavaScript in the `dist/` directory.

### Step 5: Verify Build

```bash
ls -la dist/
```

You should see:
- `index.js` - Main server file
- `index.d.ts` - TypeScript declarations
- `index.js.map` - Source maps

## Configuration

### Get Absolute Path

You'll need the absolute path to your server installation:

```bash
pwd
# Example output: /Users/username/Documents/Quickstart-Guides/mcp-screenshot-server
```

### Configure MCP Client

#### Claude Desktop

1. **Locate config file:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

2. **Edit the config file:**

```json
{
  "mcpServers": {
    "screenshot": {
      "command": "node",
      "args": [
        "/ABSOLUTE/PATH/TO/mcp-screenshot-server/dist/index.js"
      ]
    }
  }
}
```

**Important**: Replace `/ABSOLUTE/PATH/TO/` with your actual path from the `pwd` command above.

3. **Restart Claude Desktop**

#### Other MCP Clients

For other MCP clients, refer to their documentation for adding MCP servers. The server uses stdio transport and can be started with:

```bash
node /path/to/mcp-screenshot-server/dist/index.js
```

## Verification

### Test the Installation

1. **Check Node.js can run the server:**
```bash
node dist/index.js
# Should output: MCP Screenshot Server running on stdio
# Press Ctrl+C to stop
```

2. **Verify Playwright:**
```bash
npx playwright --version
```

3. **Test screenshot capability:**
```bash
# Create a simple test script
cat > test-screenshot.js << 'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto('https://example.com');
await page.screenshot({ path: 'test.png' });
await browser.close();
console.log('Screenshot saved to test.png');
EOF

node test-screenshot.js
ls -la test.png
rm test.png test-screenshot.js
```

## Troubleshooting

### "npm: command not found"

Node.js is not installed or not in your PATH. Follow the Node.js installation steps above.

### "Cannot find module '@modelcontextprotocol/sdk'"

Run `npm install` in the server directory.

### "Executable doesn't exist" (Playwright error)

Install Playwright browsers:
```bash
npx playwright install
```

### Permission Errors

Ensure you have write permissions:
```bash
chmod 755 mcp-screenshot-server
mkdir -p screenshots
chmod 755 screenshots
```

### TypeScript Compilation Errors

Ensure TypeScript is installed:
```bash
npm install
npm run build
```

## Updating

To update the server:

```bash
cd mcp-screenshot-server
git pull  # If using git
npm install  # Update dependencies
npm run build  # Rebuild
```

To update Playwright browsers:

```bash
npx playwright install --force
```

## Uninstallation

To remove the server:

```bash
# Remove from MCP config
# Edit claude_desktop_config.json and remove the "screenshot" entry

# Remove server files
rm -rf mcp-screenshot-server

# Optional: Remove Playwright browsers
rm -rf ~/Library/Caches/ms-playwright  # macOS
rm -rf ~/.cache/ms-playwright  # Linux
```

## Next Steps

Once installation is complete, see:
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [README.md](README.md) - Full documentation

