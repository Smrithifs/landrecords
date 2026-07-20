from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="/Users/smrithis/Library/Application Support/Google/Chrome/Profile 1",
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"]
        )
        page = await context.new_page()
        
        api_calls = []
        
        def handle_request(req):
            api_calls.append({
                "type": "request",
                "method": req.method,
                "url": req.url,
                "post_data": req.post_data
            })
        
        async def handle_response(res):
            try:
                body = await res.text()
                api_calls.append({
                    "type": "response", 
                    "status": res.status,
                    "url": res.url,
                    "body": body
                })
            except:
                api_calls.append({
                    "type": "response", 
                    "status": res.status,
                    "url": res.url,
                    "body": None
                })
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # Navigate to citizen portal dashboard first
        await page.goto(
            "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"
        )
        
        print("=== LOGGED IN SUCCESSFULLY ===")
        print("Now navigate to i-RTC service in the browser")
        print("Interact with ALL dropdowns")
        input("Press Enter in terminal when done...")
        
        import json
        with open("logs/debug/api_calls.json", "w") as f:
            json.dump(api_calls, f, indent=2)
        
        print(f"\nCaptured {len(api_calls)} requests")
        
        # Filter for specific request types
        keywords = ["GetDistrict", "GetTaluk", "GetHobli", "GetVillage", "GetRTC", "ViewRTC", "service37", "service78"]
        
        filtered_calls = []
        for call in api_calls:
            url = call.get("url", "")
            method = call.get("method", "")
            post_data = call.get("post_data")
            
            # POST requests to landrecords domain
            if method == "POST" and "landrecords" in url:
                filtered_calls.append(call)
            # GET requests with specific keywords
            elif method == "GET" and any(kw in url for kw in keywords):
                filtered_calls.append(call)
            # Any request with post_data not None
            elif post_data is not None:
                filtered_calls.append(call)
        
        print(f"\nFiltered API calls ({len(filtered_calls)}):")
        for call in filtered_calls:
            url = call.get("url", "")
            method = call.get("method", "")
            print(f"\n{method} {url}")
            
            if call.get("post_data"):
                print(f"  POST DATA: {call['post_data']}")
            
            if call.get("type") == "response" and call.get("body"):
                body = call["body"]
                if len(body) > 500:
                    print(f"  RESPONSE BODY: {body[:500]}...")
                else:
                    print(f"  RESPONSE BODY: {body}")
        
        await context.close()

asyncio.run(main())
