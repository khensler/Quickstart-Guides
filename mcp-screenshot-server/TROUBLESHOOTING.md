# Troubleshooting Guide

Common issues and solutions for the MCP Screenshot Server.

## Installation Issues

### "npm: command not found"

**Problem**: Node.js/npm is not installed or not in PATH.

**Solution**:
```bash
# macOS
brew install node

# Or download from https://nodejs.org/

# Verify
node --version
npm --version
```

### "Cannot find module '@modelcontextprotocol/sdk'"

**Problem**: Dependencies not installed.

**Solution**:
```bash
cd mcp-screenshot-server
npm install
```

### TypeScript Compilation Errors

**Problem**: Build fails with TypeScript errors.

**Solution**:
```bash
# Clean and rebuild
rm -rf dist node_modules
npm install
npm run build
```

## Playwright Issues

### "Executable doesn't exist at ..."

**Problem**: Playwright browsers not installed.

**Solution**:
```bash
# Install all browsers
npx playwright install

# Or just Chromium
npx playwright install chromium

# Force reinstall if corrupted
npx playwright install --force
```

### "browserType.launch: Browser closed"

**Problem**: Browser crashes on launch.

**Solution**:
```bash
# Reinstall browsers
npx playwright install --force chromium

# Check system dependencies (Linux)
npx playwright install-deps
```

### "Timeout 30000ms exceeded"

**Problem**: Page takes too long to load.

**Solution**:
- Increase `waitForTimeout` parameter
- Check network connectivity to target URL
- Verify target URL is accessible
- Try with `waitForSelector` for specific element

## MCP Configuration Issues

### Server Not Appearing in Claude Desktop

**Problem**: Server not listed in available tools.

**Solution**:
1. Check config file location:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Verify JSON syntax is valid:
```bash
# macOS
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python3 -m json.tool
```

3. Ensure absolute path is correct:
```json
{
  "mcpServers": {
    "screenshot": {
      "command": "node",
      "args": ["/FULL/ABSOLUTE/PATH/TO/dist/index.js"]
    }
  }
}
```

4. Restart Claude Desktop completely

### "Server failed to start"

**Problem**: Server crashes on startup.

**Solution**:
```bash
# Test server manually
cd mcp-screenshot-server
node dist/index.js
# Should output: "MCP Screenshot Server running on stdio"
# Press Ctrl+C to stop

# Check for errors
# If errors appear, check:
# 1. Node version: node --version (should be 18+)
# 2. Build completed: ls -la dist/index.js
# 3. Dependencies installed: ls -la node_modules
```

## Screenshot Capture Issues

### "Navigation timeout of 30000ms exceeded"

**Problem**: Page won't load.

**Solution**:
- Verify URL is accessible: `curl -I https://target-url.com`
- Check if URL requires authentication
- Try increasing timeout with `waitForTimeout`
- Check network/firewall settings

### "Element not found: selector"

**Problem**: CSS selector doesn't match any element.

**Solution**:
1. Verify selector in browser DevTools:
   - Open page in browser
   - Press F12
   - Use Console: `document.querySelector('your-selector')`

2. Wait for element to load:
```json
{
  "waitForTimeout": 3000,
  "selector": ".your-element"
}
```

3. Use more specific selector:
```json
{
  "selector": "#main-content .panel"
}
```

### Screenshots Are Blank/Black

**Problem**: Screenshot captures before content loads.

**Solution**:
```json
{
  "waitForSelector": ".content-loaded",
  "waitForTimeout": 2000
}
```

### Permission Denied Writing Screenshot

**Problem**: Cannot write to screenshots directory.

**Solution**:
```bash
# Create directory with proper permissions
mkdir -p screenshots
chmod 755 screenshots

# Or specify absolute path with write permissions
{
  "outputPath": "/Users/username/Documents/screenshots/test.png"
}
```

## Performance Issues

### Server Is Slow

**Problem**: Screenshots take a long time.

**Causes & Solutions**:

1. **First launch**: Browser initialization takes 1-2 seconds
   - Normal behavior, subsequent requests are faster

2. **Large pages**: Full page screenshots of long pages
   - Use viewport screenshots instead of `fullPage: true`
   - Use element screenshots for specific sections

3. **Network latency**: Slow connection to target
   - Use local network when possible
   - Increase timeout values

### High Memory Usage

**Problem**: Server uses too much memory.

**Solution**:
- Browser instances are reused but stay in memory
- Restart Claude Desktop to clear browser instances
- Use only one browser type when possible

## Lab Environment Issues

### Cannot Access Local Lab URLs

**Problem**: Screenshots fail for local network addresses.

**Solution**:
1. Verify connectivity:
```bash
ping proxmox.lab
curl -k https://proxmox.lab:8006
```

2. Check DNS resolution:
```bash
# Add to /etc/hosts if needed
echo "192.168.1.100 proxmox.lab" | sudo tee -a /etc/hosts
```

3. Handle self-signed certificates:
   - Playwright accepts self-signed certs by default
   - If issues persist, check firewall rules

### Authentication Required

**Problem**: Page requires login.

**Current Limitation**: The server doesn't handle complex authentication flows.

**Workarounds**:
1. Use URLs that don't require auth (if available)
2. Configure target system for IP-based access
3. Future enhancement: Add cookie/session support

## Debugging

### Enable Verbose Logging

```bash
# Run server with debug output
DEBUG=pw:api node dist/index.js
```

### Check MCP Logs

**Claude Desktop Logs**:
- macOS: `~/Library/Logs/Claude/`
- Windows: `%APPDATA%\Claude\logs\`

### Test Playwright Directly

```bash
# Create test script
cat > test.js << 'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: false });
const page = await browser.newPage();
await page.goto('https://example.com');
await page.screenshot({ path: 'test.png' });
await browser.close();
EOF

node test.js
```

### Verify Setup

```bash
# Run setup checker
./check-setup.sh
```

## Getting More Help

If issues persist:

1. **Check versions**:
```bash
node --version
npm --version
npx playwright --version
```

2. **Collect diagnostic info**:
```bash
# System info
uname -a

# Node info
node --version
npm --version

# Playwright info
npx playwright --version

# Server build
ls -la dist/

# Dependencies
npm list --depth=0
```

3. **Common fixes**:
```bash
# Nuclear option: complete reinstall
rm -rf node_modules dist
npm install
npm run build
npx playwright install chromium
```

## Known Limitations

- No support for complex authentication flows
- Cannot capture native applications
- Requires graphical environment (even in headless mode)
- Some dynamic content may require custom wait conditions
- WebKit may have rendering differences from Chromium

## Still Having Issues?

1. Review [INSTALLATION.md](INSTALLATION.md)
2. Review [QUICKSTART.md](QUICKSTART.md)
3. Check Playwright documentation: https://playwright.dev/
4. Check MCP documentation: https://modelcontextprotocol.io/

