import asyncio
from dotenv import load_dotenv
from typing import Awaitable, Callable
from mcp.server.fastmcp import FastMCP, Context
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("browser-use")

browser = Browser(
    config=BrowserConfig(
        chrome_instance_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222",
        headless=True
    )
)

llm = ChatOpenAI(model="gpt-4o")
agent = None


@mcp.tool()
async def perform_search(task: str, context: Context):
    """Perform the actual search in the background."""
    async def step_handler(state, *args):
        if len(args) != 2:
            return
        await context.session.send_log_message(
            level="info",
            data={"screenshot": state.screenshot, "result": args[0]}
        )

    asyncio.create_task(
        run_browser_agent(task=task, on_step=step_handler)
    )
    return "Processing Request"


@mcp.tool()
async def stop_search(*, context: Context):
    """Stop a running browser agent search by task ID."""
    if agent is not None:
        await agent.stop()
    return "Running Agent stopped"


async def run_browser_agent(task: str, on_step: Callable[[], Awaitable[None]]):
    """Run the browser-use agent with the specified task."""
    global agent
    try:
        agent = Agent(
            task=task,
            browser=browser,
            llm=llm,
            register_new_step_callback=on_step,
            register_done_callback=on_step,
        )

        await agent.run()
    except asyncio.CancelledError:
        return "Task was cancelled"

    except Exception as e:
        return f"Error during execution: {str(e)}"
    finally:
        await browser.close()

if __name__ == "__main__":
    mcp.run(transport="sse")
