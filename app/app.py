import contextvars
import os
import time
import asyncio
from browser_use.agent.service import AgentOutput, BrowserContext, BrowserState
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from browser_use import Agent, AgentHistoryList, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from langchain_openai import ChatOpenAI

from app.custom_browser import CustomBrowser
from app.util.helper import calculate_total_token

load_dotenv()

mcp = FastMCP("browser-use")

llm = ChatOpenAI(model="gpt-4o")

TASK_MAX_TIME_SECONDS = os.getenv("TASK_MAX_TIME_SECONDS", "300")

@mcp.tool()
async def perform_search(task: str, request_id: str, context: Context):
    """Perform the actual search in the background."""
    asyncio.create_task(run_browser_agent(request_id=request_id, task=task, context=context))
    return "Processing Request"

async def run_browser_agent(
        request_id: str,
        task: str, 
        context: Context,
    ):
    """Run the browser-use agent with the specified task."""
    browser = CustomBrowser(
        config=BrowserConfig(
            browser_binary_path="/usr/bin/chromium",
            headless=False,
            extra_browser_args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920x1080",
                # Additional Tuning features on browser
                "--enable-pinch",
                "--disable-field-trial-config",
                "--disable-features=TFLiteLanguageDetectionEnabled",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-back-forward-cache",
                "--disable-breakpad",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-component-update",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-features=ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls,MediaRouter,DialMediaRouteProvider,AcceptCHFrame,AutoExpandDetailsElement,CertificateTransparencyComponentUpdater,AvoidUnnecessaryBeforeUnloadCheckSync,Translate,HttpsUpgrades,PaintHolding",
                "--disable-hang-monitor",
                "--disable-ipc-flooding-protection",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-renderer-backgrounding",
                "--force-color-profile=srgb",
                "--allow-pre-commit-input",
                "--metrics-recording-only",
                "--password-store=basic",
                "--use-mock-keychain",
                "--no-service-autorun",
                "--no-first-run",
                "--export-tagged-pdf",
                "--disable-search-engine-choice-screen",
                "--noerrdialogs",
                "--mute-audio",
                # Enable features
                "--enable-features=NetworkService,NetworkServiceInProcess",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                f"--user-data-dir=/root/.config/browseruse/profiles/{request_id}",
                "--load-extension=/app/extensions/ulite"
            ],
        )
    )
    browser_context = BrowserContext(
            browser=browser,
            config=BrowserContextConfig(
                highlight_elements=False,
                window_width=1920,
                window_height=1080,
                no_viewport=False,
            )
        )

    agent = None

    async def step_handler(state: BrowserState, agent_output: AgentOutput, step_no):
        current_total = 0
        if agent:
            current_total = calculate_total_token(agent.state.history)
            print(f"Current : Count {current_total}")

        await context.session.send_log_message(
            level="info",
            data={"screenshot": state.screenshot, "result": agent_output, "step_no": step_no, "request_id": request_id, "is_last": False, "total_token": current_total}
    )

    async def done_handler(historyList: AgentHistoryList):
        total = calculate_total_token(historyList)

        await context.session.send_log_message(
            level="info",
            data={"request_id": request_id, "is_last": True, "total_token": total}
        )


    agent = Agent(
        task=task,
        browser=browser,
        browser_context=browser_context,
        enable_memory=False,
        llm=llm,
        register_new_step_callback=step_handler,
        register_done_callback=done_handler,
        extend_system_message="#Additional NAVIGATION & ERROR HANDLING = If stuck on same screen, summarize and conclude the task. DO NOT attempt to LOGIN sites that require LOGIN, just conclude the task"
    )
    
    start_time = time.monotonic()

    async def on_step_end_handler(agent: Agent):
        end_time = time.monotonic()
        elapsed = end_time - start_time

        print(f"Request {request_id} Elapsed time: {elapsed:.2f} seconds")
        if elapsed > float(TASK_MAX_TIME_SECONDS):
            print(f"{request_id}: Exceeded time stopping agent and responding.")
            current_total = calculate_total_token(agent.state.history)
            agent.stop()

            await context.session.send_log_message(
                level="info",
                data={"request_id": request_id, "is_last": True, "total_token": current_total, "timeout_summary": "Sorry, Ran out of time to complete the tasks, perhaps provide smaller tasks for the browser visualizer function."}
            )
    
    try:
        await agent.run(
            max_steps=20,
            on_step_end=on_step_end_handler
        )
    except asyncio.CancelledError:
        return "Task was cancelled"

    except Exception as e:
        return f"Error during execution: {str(e)}"
    finally:
        print("[Agent] cleaning up agent")
        await browser_context.close()
        await browser.close()
        await agent.close()

