# MCP Screenshot Server - Project Overview

## What is This?

The MCP Screenshot Server is a **Model Context Protocol (MCP) server** that enables AI assistants like Claude to capture screenshots from web pages using Playwright. It's specifically designed for documenting lab environments and creating technical documentation.

## Why Use This?

### Problem It Solves

When documenting lab environments (like Proxmox, storage arrays, network devices), you often need to:
- Capture consistent screenshots of web interfaces
- Document configuration screens
- Create step-by-step visual guides
- Verify web interfaces are loading correctly

Doing this manually is time-consuming and error-prone. This server automates the entire process.

### Key Benefits

1. **Automation** - Capture screenshots through natural language commands
2. **Consistency** - Same viewport sizes, same browser, repeatable results
3. **Flexibility** - Full page, specific elements, multiple browsers
4. **Integration** - Works directly with Claude Desktop and other MCP clients
5. **Lab-Friendly** - Handles authentication, custom ports, local networks

## Architecture

```
┌─────────────────┐
│  Claude Desktop │
│   (MCP Client)  │
└────────┬────────┘
         │ MCP Protocol (stdio)
         │
┌────────▼────────────────────┐
│  MCP Screenshot Server      │
│  - Tool definitions         │
│  - Request handling         │
│  - Browser management       │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│     Playwright              │
│  - Chromium/Firefox/WebKit  │
│  - Page automation          │
│  - Screenshot capture       │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│   Target Web Pages          │
│  - Proxmox interfaces       │
│  - Storage dashboards       │
│  - Network devices          │
│  - Documentation sites      │
└─────────────────────────────┘
```

## Project Structure

```
mcp-screenshot-server/
├── src/
│   └── index.ts              # Main server implementation
├── dist/                     # Compiled JavaScript (generated)
│   └── index.js
├── screenshots/              # Default output directory (generated)
├── package.json              # Dependencies and scripts
├── tsconfig.json             # TypeScript configuration
├── README.md                 # Main documentation
├── INSTALLATION.md           # Installation guide
├── QUICKSTART.md             # Quick start guide
├── PROJECT-OVERVIEW.md       # This file
├── example-config.json       # Example MCP configuration
├── check-setup.sh            # Setup verification script
├── .gitignore                # Git ignore rules
└── .npmignore                # npm ignore rules
```

## Technology Stack

- **TypeScript** - Type-safe development
- **Node.js** - Runtime environment
- **Playwright** - Browser automation
  - Chromium (default)
  - Firefox
  - WebKit
- **MCP SDK** - Model Context Protocol implementation

## How It Works

### 1. Server Startup

```typescript
// Server starts and listens on stdio
const server = new ScreenshotServer();
server.run();
```

### 2. Tool Registration

The server registers three tools:
- `capture_screenshot` - Full page or viewport screenshots
- `capture_element_screenshot` - Element-specific screenshots
- `navigate_and_wait` - Page load testing

### 3. Request Handling

```
User → Claude → MCP Request → Screenshot Server → Playwright → Browser → Screenshot
```

### 4. Browser Management

- Browsers are launched on-demand
- Instances are reused for efficiency
- Automatic cleanup on shutdown

### 5. Screenshot Capture

```typescript
// Navigate to page
await page.goto(url);

// Wait for conditions
await page.waitForSelector(selector);

// Capture screenshot
await page.screenshot({ path: outputPath });
```

## Use Cases

### 1. Documentation Generation

**Scenario**: Creating a Proxmox setup guide

```
"Capture screenshots of the following Proxmox pages:
1. Dashboard at https://proxmox.lab:8006
2. Storage configuration
3. Network settings
Save them as proxmox-dashboard.png, proxmox-storage.png, proxmox-network.png"
```

### 2. Lab Verification

**Scenario**: Verify all services are running

```
"Navigate to each of these URLs and capture screenshots:
- https://storage.lab/admin
- https://switch.lab
- https://monitoring.lab:3000
Wait for each page to fully load"
```

### 3. Training Materials

**Scenario**: Create consistent screenshots for training

```
"Capture full page screenshots of the setup wizard at 
https://app.lab/setup with viewport 1920x1080"
```

### 4. Troubleshooting Documentation

**Scenario**: Document an error state

```
"Capture a screenshot of the error message on 
https://app.lab/dashboard using selector '.error-panel'"
```

## Configuration Options

### Viewport Customization

```json
{
  "width": 1920,
  "height": 1080
}
```

### Browser Selection

```json
{
  "browser": "chromium"  // or "firefox", "webkit"
}
```

### Wait Conditions

```json
{
  "waitForSelector": ".content-loaded",
  "waitForTimeout": 3000
}
```

### Clipping Regions

```json
{
  "clip": {
    "x": 100,
    "y": 100,
    "width": 800,
    "height": 600
  }
}
```

## Development Workflow

### Making Changes

1. Edit `src/index.ts`
2. Run `npm run watch` (auto-rebuild)
3. Restart Claude Desktop
4. Test changes

### Adding New Tools

1. Define tool schema in `getTools()`
2. Add handler in `CallToolRequestSchema`
3. Implement method
4. Update documentation

### Debugging

```bash
# Check server can start
node dist/index.js

# View MCP logs in Claude Desktop
# macOS: ~/Library/Logs/Claude/
```

## Security Considerations

- Server runs locally only (stdio transport)
- No network exposure
- Screenshots saved to local filesystem
- Browser instances isolated per request
- No credential storage

## Performance

- **Browser Launch**: ~1-2 seconds (first time)
- **Browser Reuse**: ~100ms (subsequent requests)
- **Screenshot Capture**: ~500ms - 2s (depends on page)
- **Memory**: ~100-200MB per browser instance

## Limitations

- Requires Node.js 18+
- Playwright browsers need ~300MB disk space each
- Cannot capture content requiring complex authentication flows
- Limited to web content (no native apps)

## Future Enhancements

Potential additions:
- PDF generation
- Video recording
- Network request interception
- Cookie/session management
- Batch screenshot operations
- Screenshot comparison
- Annotation support

## Getting Help

1. Check [INSTALLATION.md](INSTALLATION.md) for setup issues
2. Check [QUICKSTART.md](QUICKSTART.md) for usage examples
3. Run `./check-setup.sh` to verify installation
4. Check Playwright docs: https://playwright.dev/
5. Check MCP docs: https://modelcontextprotocol.io/

## Contributing

To contribute:
1. Fork the repository
2. Create a feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## License

MIT License - See LICENSE file for details

