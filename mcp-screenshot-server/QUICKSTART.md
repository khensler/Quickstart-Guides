# Quick Start Guide

Get started with the MCP Screenshot Server in 5 minutes.

## Step 1: Install Dependencies

```bash
cd mcp-screenshot-server
npm install
```

## Step 2: Install Playwright Browsers

```bash
npx playwright install chromium
# Optional: Install other browsers
npx playwright install firefox webkit
```

## Step 3: Build the Server

```bash
npm run build
```

## Step 4: Configure MCP Client

### For Claude Desktop

1. Find your config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add the server configuration:

```json
{
  "mcpServers": {
    "screenshot": {
      "command": "node",
      "args": [
        "/Users/YOUR_USERNAME/path/to/mcp-screenshot-server/dist/index.js"
      ]
    }
  }
}
```

**Important**: Replace `/Users/YOUR_USERNAME/path/to/` with the actual absolute path to your installation.

3. Restart Claude Desktop

## Step 5: Test the Server

In Claude Desktop, try these commands:

### Test 1: Basic Screenshot
```
Capture a screenshot of https://example.com
```

### Test 2: Full Page Screenshot
```
Capture a full page screenshot of https://github.com with width 1920 and height 1080
```

### Test 3: Element Screenshot
```
Capture a screenshot of the main heading on https://example.com using selector "h1"
```

## Verify Installation

Check that screenshots are being saved:

```bash
ls -la screenshots/
```

You should see PNG files with timestamps.

## Troubleshooting

### Server Not Starting

1. Check the MCP logs in Claude Desktop
2. Verify the path in your config is absolute and correct
3. Ensure Node.js is installed: `node --version`
4. Ensure the build completed: check for `dist/index.js`

### Playwright Errors

If you see browser-related errors:

```bash
# Reinstall browsers
npx playwright install --force
```

### Permission Errors

Ensure the screenshots directory is writable:

```bash
mkdir -p screenshots
chmod 755 screenshots
```

## Next Steps

- Read the full [README.md](README.md) for all available tools
- Explore advanced features like viewport customization and clipping
- Use different browsers (chromium, firefox, webkit)
- Integrate with your lab documentation workflow

## Common Use Cases

### Document Proxmox Configuration

```
Capture screenshots of my Proxmox dashboard at https://proxmox.lab:8006
Use browser chromium and wait 3000ms for the page to fully load
```

### Capture Storage Interface

```
Navigate to https://storage.lab/admin and capture a screenshot of the 
storage pools section using selector "#storage-pools"
```

### Full Page Documentation

```
Capture a full page screenshot of https://docs.example.com/setup-guide
Save it as "setup-guide-full.png"
```

## Development Mode

For active development:

```bash
# Terminal 1: Watch for changes
npm run watch

# Terminal 2: Test changes
# Restart Claude Desktop after each build
```

