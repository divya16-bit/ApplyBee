import asyncio

# Limit to 3 concurrent Playwright browser instances
# Adjust this number based on your server capacity
playwright_semaphore = asyncio.Semaphore(3)