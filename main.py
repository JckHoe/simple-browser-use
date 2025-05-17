import asyncio
from dotenv import load_dotenv
from typing import Awaitable, Callable
from mcp.server.fastmcp import FastMCP, Context
from browser_use import Agent, AgentHistoryList, Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from langchain_openai import ChatOpenAI

load_dotenv()

mcp = FastMCP("browser-use")

browser = Browser(
    config=BrowserConfig(
        browser_binary_path="/usr/bin/chromium",
        headless=True,
        extra_browser_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
            "--window-size=1920x1080",
            "--remote-debugging-port=9222"
        ],
    )
)


llm = ChatOpenAI(model="gpt-4o")

@mcp.tool()
async def perform_search(task: str, request_id: str, context: Context):
    """Perform the actual search in the background."""
    async def step_handler(state, *args):
        if len(args) != 2:
            return
        await context.session.send_log_message(
            level="info",
            data={"screenshot": state.screenshot, "result": args[0], "request_id": request_id, "last": False}
        )

    async def done_handler(historyList: AgentHistoryList):
        total = 0
        for h in historyList.history:
            if h.metadata:
                total += h.metadata.input_tokens

        await context.session.send_log_message(
            level="info",
            data={"request_id": request_id, "last": True, "total_token": total}
        )


    asyncio.create_task(
        run_browser_agent(task=task, on_step=step_handler, on_done=done_handler)
    )
    return "Processing Request"


async def run_browser_agent(task: str, on_step: Callable[[], Awaitable[None]], on_done: Callable[['AgentHistoryList'], Awaitable[None]]):
    """Run the browser-use agent with the specified task."""
    context=BrowserContext(
        browser=browser,
        config=BrowserContextConfig(
            highlight_elements=False,
            window_width=1920,
            window_height=1080,
            no_viewport=False,
        )
    )
    agent = Agent(
        task=task,
        browser=browser,
        browser_context=context,
        llm=llm,
        register_new_step_callback=on_step,
        register_done_callback=on_done,
        extend_system_message="#Additional NAVIGATION & ERROR HANDLING = If stuck on same screen, summarize and conclude the task"
    )
    
    try:
        await agent.run()
    except asyncio.CancelledError:
        return "Task was cancelled"

    except Exception as e:
        return f"Error during execution: {str(e)}"
    finally:
        await context.close()
        await browser.close()
        await agent.close()

if __name__ == "__main__":
    mcp.run(transport="sse")
