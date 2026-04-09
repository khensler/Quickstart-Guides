# MCP Screenshot Server

A Model Context Protocol (MCP) server for capturing screenshots from lab environments using Playwright. This server provides tools for automated screenshot capture, element-specific screenshots, and page navigation testing.

## Features

- 📸 **Full Page Screenshots** - Capture entire scrollable pages
- 🎯 **Element Screenshots** - Capture specific elements by CSS selector
- 🌐 **Multi-Browser Support** - Chromium, Firefox, and WebKit
- ⚙️ **Flexible Configuration** - Custom viewport sizes, wait conditions, and clipping regions
- 🔄 **Browser Reuse** - Efficient browser instance management
- 📁 **Automatic Organization** - Screenshots saved to organized directory structure

## Installation

```bash
cd mcp-screenshot-server
npm install
npm run build
```

### Install Playwright Browsers

```bash
npx playwright install
```

## Configuration

Add to your MCP settings file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "screenshot": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-screenshot-server/dist/index.js"]
    }
  }
}
```

## Available Tools

### 1. capture_screenshot

Capture a screenshot of a web page with extensive customization options.

**Parameters:**
- `url` (required): The URL of the page to capture
- `outputPath` (optional): Custom filename or path for the screenshot
- `fullPage` (optional): Capture the full scrollable page (default: false)
- `width` (optional): Viewport width in pixels (default: 1280)
- `height` (optional): Viewport height in pixels (default: 720)
- `browser` (optional): Browser to use - "chromium", "firefox", or "webkit" (default: "chromium")
- `waitForSelector` (optional): CSS selector to wait for before capturing
- `waitForTimeout` (optional): Additional wait time in milliseconds
- `clip` (optional): Clip region with x, y, width, height properties

**Example:**
```json
{
  "url": "https://example.com",
  "fullPage": true,
  "width": 1920,
  "height": 1080,
  "outputPath": "example-full.png"
}
```

### 2. capture_element_screenshot

Capture a screenshot of a specific element on a page.

**Parameters:**
- `url` (required): The URL of the page
- `selector` (required): CSS selector for the element to capture
- `outputPath` (optional): Custom filename or path
- `browser` (optional): Browser to use (default: "chromium")
- `waitForTimeout` (optional): Additional wait time in milliseconds

**Example:**
```json
{
  "url": "https://example.com",
  "selector": "#main-content",
  "outputPath": "main-content.png"
}
```

### 3. navigate_and_wait

Navigate to a URL and wait for specific conditions (useful for testing page load).

**Parameters:**
- `url` (required): The URL to navigate to
- `waitForSelector` (optional): CSS selector to wait for
- `waitForTimeout` (optional): Time to wait in milliseconds
- `browser` (optional): Browser to use (default: "chromium")

**Example:**
```json
{
  "url": "https://example.com",
  "waitForSelector": ".content-loaded",
  "waitForTimeout": 2000
}
```

## Usage Examples

### Capture a Full Page Screenshot

```
Please capture a full page screenshot of https://example.com
```

### Capture Specific Element

```
Capture a screenshot of the navigation menu at https://example.com using selector "nav.main-menu"
```

### Test Page Load

```
Navigate to https://example.com and wait for the selector ".dashboard-loaded"
```

### Lab Environment Documentation

```
Capture screenshots of the following Proxmox interfaces:
1. Dashboard at https://proxmox.lab:8006
2. Storage configuration page
3. Network settings
```

## Output

Screenshots are saved to the `screenshots/` directory in the current working directory by default. Each screenshot is timestamped automatically if no custom output path is provided.

## Development

```bash
# Watch mode for development
npm run watch

# Build
npm run build
```

## Use Cases for Lab Environments

- 📚 **Documentation** - Automatically capture UI screenshots for guides
- 🧪 **Testing** - Verify web interfaces are loading correctly
- 📊 **Monitoring** - Capture dashboard states at intervals
- 🔍 **Troubleshooting** - Document error states and configurations
- 📝 **Training Materials** - Generate consistent screenshots for tutorials

### Perfect for HPE Virtual Machine Essentials (VME)

This server is ideal for documenting **HPE VME NFS and iSCSI configurations**:
- 🖥️ Capture VME web interface screenshots
- 💾 Document NFS datastore configurations
- 🔌 Document iSCSI initiator and target setup
- 🌐 Capture network configuration for storage traffic
- 📋 Create step-by-step setup guides
- ✅ Verify storage integration

See [HPE-VME-WORKFLOW.md](HPE-VME-WORKFLOW.md) for detailed HPE VME documentation workflows and [HPE-VME-TEMPLATES.md](HPE-VME-TEMPLATES.md) for ready-to-use screenshot templates.

## License

MIT

