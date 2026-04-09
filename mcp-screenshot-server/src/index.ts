#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium, firefox, webkit, Browser, BrowserContext, Page } from "playwright";
import { promises as fs } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default screenshot directory
const DEFAULT_SCREENSHOT_DIR = path.join(process.cwd(), "screenshots");

interface ScreenshotArgs {
  url: string;
  outputPath?: string;
  fullPage?: boolean;
  width?: number;
  height?: number;
  browser?: "chromium" | "firefox" | "webkit";
  waitForSelector?: string;
  waitForTimeout?: number;
  clip?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface ScreenshotElementArgs {
  url: string;
  selector: string;
  outputPath?: string;
  browser?: "chromium" | "firefox" | "webkit";
  waitForTimeout?: number;
}

interface NavigateAndWaitArgs {
  url: string;
  waitForSelector?: string;
  waitForTimeout?: number;
  browser?: "chromium" | "firefox" | "webkit";
}

class ScreenshotServer {
  private server: Server;
  private browserInstances: Map<string, Browser> = new Map();

  constructor() {
    this.server = new Server(
      {
        name: "mcp-screenshot-server",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
    this.setupErrorHandling();
  }

  private setupErrorHandling(): void {
    this.server.onerror = (error) => {
      console.error("[MCP Error]", error);
    };

    process.on("SIGINT", async () => {
      await this.cleanup();
      process.exit(0);
    });
  }

  private async cleanup(): Promise<void> {
    for (const [name, browser] of this.browserInstances) {
      console.error(`Closing browser: ${name}`);
      await browser.close();
    }
    this.browserInstances.clear();
  }

  private async getBrowser(browserType: "chromium" | "firefox" | "webkit" = "chromium"): Promise<Browser> {
    if (!this.browserInstances.has(browserType)) {
      let browser: Browser;
      switch (browserType) {
        case "firefox":
          browser = await firefox.launch();
          break;
        case "webkit":
          browser = await webkit.launch();
          break;
        default:
          browser = await chromium.launch();
      }
      this.browserInstances.set(browserType, browser);
    }
    return this.browserInstances.get(browserType)!;
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: this.getTools(),
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case "capture_screenshot":
            return await this.captureScreenshot(args as ScreenshotArgs);
          case "capture_element_screenshot":
            return await this.captureElementScreenshot(args as ScreenshotElementArgs);
          case "navigate_and_wait":
            return await this.navigateAndWait(args as NavigateAndWaitArgs);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text",
              text: `Error: ${errorMessage}`,
            },
          ],
        };
      }
    });
  }

  private getTools(): Tool[] {
    return [
      {
        name: "capture_screenshot",
        description: "Capture a screenshot of a web page. Supports full page screenshots, custom viewport sizes, and clipping regions.",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "The URL of the page to capture",
            },
            outputPath: {
              type: "string",
              description: "Optional output path for the screenshot (relative to screenshots directory or absolute path)",
            },
            fullPage: {
              type: "boolean",
              description: "Whether to capture the full scrollable page (default: false)",
              default: false,
            },
            width: {
              type: "number",
              description: "Viewport width in pixels (default: 1280)",
              default: 1280,
            },
            height: {
              type: "number",
              description: "Viewport height in pixels (default: 720)",
              default: 720,
            },
            browser: {
              type: "string",
              enum: ["chromium", "firefox", "webkit"],
              description: "Browser to use (default: chromium)",
              default: "chromium",
            },
            waitForSelector: {
              type: "string",
              description: "CSS selector to wait for before taking screenshot",
            },
            waitForTimeout: {
              type: "number",
              description: "Additional time to wait in milliseconds after page load",
            },
            clip: {
              type: "object",
              description: "Clip region for screenshot",
              properties: {
                x: { type: "number" },
                y: { type: "number" },
                width: { type: "number" },
                height: { type: "number" },
              },
            },
          },
          required: ["url"],
        },
      },
      {
        name: "capture_element_screenshot",
        description: "Capture a screenshot of a specific element on a web page",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "The URL of the page containing the element",
            },
            selector: {
              type: "string",
              description: "CSS selector for the element to capture",
            },
            outputPath: {
              type: "string",
              description: "Optional output path for the screenshot",
            },
            browser: {
              type: "string",
              enum: ["chromium", "firefox", "webkit"],
              description: "Browser to use (default: chromium)",
              default: "chromium",
            },
            waitForTimeout: {
              type: "number",
              description: "Additional time to wait in milliseconds after page load",
            },
          },
          required: ["url", "selector"],
        },
      },
      {
        name: "navigate_and_wait",
        description: "Navigate to a URL and wait for specific conditions (useful for testing page load)",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "The URL to navigate to",
            },
            waitForSelector: {
              type: "string",
              description: "CSS selector to wait for",
            },
            waitForTimeout: {
              type: "number",
              description: "Time to wait in milliseconds",
            },
            browser: {
              type: "string",
              enum: ["chromium", "firefox", "webkit"],
              description: "Browser to use (default: chromium)",
              default: "chromium",
            },
          },
          required: ["url"],
        },
      },
    ];
  }


  private async captureScreenshot(args: ScreenshotArgs) {
    const {
      url,
      outputPath,
      fullPage = false,
      width = 1280,
      height = 720,
      browser: browserType = "chromium",
      waitForSelector,
      waitForTimeout,
      clip,
    } = args;

    const browser = await this.getBrowser(browserType);
    const context = await browser.newContext({
      viewport: { width, height },
    });
    const page = await context.newPage();

    try {
      await page.goto(url, { waitUntil: "networkidle" });

      if (waitForSelector) {
        await page.waitForSelector(waitForSelector, { timeout: 30000 });
      }

      if (waitForTimeout) {
        await page.waitForTimeout(waitForTimeout);
      }

      // Ensure screenshot directory exists
      await fs.mkdir(DEFAULT_SCREENSHOT_DIR, { recursive: true });

      // Generate output path
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const filename = outputPath || `screenshot-${timestamp}.png`;
      const fullPath = path.isAbsolute(filename)
        ? filename
        : path.join(DEFAULT_SCREENSHOT_DIR, filename);

      await page.screenshot({
        path: fullPath,
        fullPage,
        clip,
      });

      await context.close();

      return {
        content: [
          {
            type: "text",
            text: `Screenshot captured successfully!\nPath: ${fullPath}\nURL: ${url}\nBrowser: ${browserType}\nViewport: ${width}x${height}\nFull page: ${fullPage}`,
          },
        ],
      };
    } catch (error) {
      await context.close();
      throw error;
    }
  }

  private async captureElementScreenshot(args: ScreenshotElementArgs) {
    const {
      url,
      selector,
      outputPath,
      browser: browserType = "chromium",
      waitForTimeout,
    } = args;

    const browser = await this.getBrowser(browserType);
    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      await page.goto(url, { waitUntil: "networkidle" });

      if (waitForTimeout) {
        await page.waitForTimeout(waitForTimeout);
      }

      const element = await page.waitForSelector(selector, { timeout: 30000 });
      if (!element) {
        throw new Error(`Element not found: ${selector}`);
      }

      // Ensure screenshot directory exists
      await fs.mkdir(DEFAULT_SCREENSHOT_DIR, { recursive: true });

      // Generate output path
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const filename = outputPath || `element-${timestamp}.png`;
      const fullPath = path.isAbsolute(filename)
        ? filename
        : path.join(DEFAULT_SCREENSHOT_DIR, filename);

      await element.screenshot({ path: fullPath });

      await context.close();

      return {
        content: [
          {
            type: "text",
            text: `Element screenshot captured successfully!\nPath: ${fullPath}\nURL: ${url}\nSelector: ${selector}\nBrowser: ${browserType}`,
          },
        ],
      };
    } catch (error) {
      await context.close();
      throw error;
    }
  }

  private async navigateAndWait(args: NavigateAndWaitArgs) {
    const {
      url,
      waitForSelector,
      waitForTimeout,
      browser: browserType = "chromium",
    } = args;

    const browser = await this.getBrowser(browserType);
    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      const startTime = Date.now();
      await page.goto(url, { waitUntil: "networkidle" });
      const loadTime = Date.now() - startTime;

      if (waitForSelector) {
        await page.waitForSelector(waitForSelector, { timeout: 30000 });
      }

      if (waitForTimeout) {
        await page.waitForTimeout(waitForTimeout);
      }

      const title = await page.title();
      await context.close();

      return {
        content: [
          {
            type: "text",
            text: `Navigation successful!\nURL: ${url}\nTitle: ${title}\nLoad time: ${loadTime}ms\nBrowser: ${browserType}`,
          },
        ],
      };
    } catch (error) {
      await context.close();
      throw error;
    }
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("MCP Screenshot Server running on stdio");
  }
}

const server = new ScreenshotServer();
server.run().catch(console.error);

