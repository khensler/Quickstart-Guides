# Get Started with MCP Screenshot Server

**Quick reference for getting up and running in minutes.**

## What You Need

- ✅ macOS, Linux, or Windows
- ✅ 10 minutes of time
- ✅ Basic command line knowledge

## Installation Steps

### 1️⃣ Install Node.js (if not already installed)

**macOS**:
```bash
brew install node
```

**Linux (Ubuntu/Debian)**:
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Windows**: Download from https://nodejs.org/

**Verify**:
```bash
node --version  # Should show v18 or higher
```

### 2️⃣ Install Dependencies

```bash
cd mcp-screenshot-server
npm install
```

### 3️⃣ Install Playwright Browsers

```bash
npx playwright install chromium
```

### 4️⃣ Build the Server

```bash
npm run build
```

### 5️⃣ Get the Absolute Path

```bash
pwd
# Copy this path - you'll need it for configuration
```

### 6️⃣ Configure Claude Desktop

**Find your config file**:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Edit the file** (create if it doesn't exist):
```json
{
  "mcpServers": {
    "screenshot": {
      "command": "node",
      "args": [
        "/PASTE/YOUR/PATH/HERE/mcp-screenshot-server/dist/index.js"
      ]
    }
  }
}
```

**Important**: Replace `/PASTE/YOUR/PATH/HERE/` with the path from step 5.

### 7️⃣ Restart Claude Desktop

Completely quit and restart Claude Desktop.

### 8️⃣ Test It!

In Claude Desktop, try:
```
Capture a screenshot of https://example.com
```

You should see a success message with the screenshot path!

## Verify Installation

Run the setup checker:
```bash
./check-setup.sh
```

This will verify all components are installed correctly.

## Quick Reference

### Basic Screenshot
```
Capture a screenshot of https://example.com
```

### Full Page Screenshot
```
Capture a full page screenshot of https://github.com
```

### Custom Size
```
Capture a screenshot of https://example.com with width 1920 and height 1080
```

### Element Screenshot
```
Capture a screenshot of the main heading on https://example.com using selector "h1"
```

### Lab Environment
```
Capture a screenshot of https://proxmox.lab:8006
Wait 3000ms for the page to load
Save as proxmox-dashboard.png
```

## Where Are Screenshots Saved?

By default: `mcp-screenshot-server/screenshots/`

Each screenshot is automatically timestamped unless you specify a custom name.

## Common Issues

### "npm: command not found"
→ Install Node.js (see step 1)

### "Server not appearing in Claude"
→ Check config file path is absolute
→ Restart Claude Desktop completely

### "Executable doesn't exist"
→ Run: `npx playwright install chromium`

### Still having issues?
→ Run: `./check-setup.sh`
→ See: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Next Steps

📚 **Learn More**:
- [README.md](README.md) - Full documentation
- [EXAMPLES.md](EXAMPLES.md) - Real-world usage examples
- [PROJECT-OVERVIEW.md](PROJECT-OVERVIEW.md) - Architecture and design

🔧 **Advanced Setup**:
- [INSTALLATION.md](INSTALLATION.md) - Detailed installation guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Problem solving

## Use Cases

Perfect for:
- 📸 Documenting lab environments (Proxmox, storage arrays, network devices)
- 📝 Creating technical documentation
- 🧪 Testing web interfaces
- 📊 Capturing dashboard states
- 🎓 Generating training materials

## File Structure

```
mcp-screenshot-server/
├── src/index.ts          # Source code
├── dist/index.js         # Built server (run this)
├── screenshots/          # Output directory
├── package.json          # Dependencies
└── Documentation files
```

## Development Mode

Want to modify the server?

```bash
# Terminal 1: Auto-rebuild on changes
npm run watch

# Terminal 2: Make changes to src/index.ts
# Restart Claude Desktop to test
```

## Getting Help

1. ✅ Run `./check-setup.sh` to verify installation
2. 📖 Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. 📚 Review [EXAMPLES.md](EXAMPLES.md) for usage patterns
4. 🔍 Check Playwright docs: https://playwright.dev/

## Success Checklist

- [ ] Node.js installed (v18+)
- [ ] Dependencies installed (`npm install`)
- [ ] Playwright browsers installed (`npx playwright install chromium`)
- [ ] Server built (`npm run build`)
- [ ] Config file updated with absolute path
- [ ] Claude Desktop restarted
- [ ] Test screenshot successful

Once all items are checked, you're ready to go! 🎉

## Quick Commands

```bash
# Check setup
./check-setup.sh

# Rebuild server
npm run build

# Watch for changes
npm run watch

# Install/reinstall browsers
npx playwright install chromium

# Test server manually
node dist/index.js
# (Press Ctrl+C to stop)
```

## Tips

💡 **Use absolute paths** in config file
💡 **Wait for page load** with `waitForTimeout` or `waitForSelector`
💡 **Name your screenshots** for easy organization
💡 **Use consistent viewports** for documentation
💡 **Test selectors** in browser DevTools first

---

**Ready to capture some screenshots?** 📸

Start with a simple test:
```
Capture a screenshot of https://example.com and save it as my-first-screenshot.png
```

