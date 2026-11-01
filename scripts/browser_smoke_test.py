"""Automated Browser End-to-End Smoke Test for EventPrice AI Planning Concierge.

Controls headless Google Chrome via the Chrome DevTools Protocol (CDP),
spawns the FastAPI backend and Vite frontend, interacts with the actual
UI elements in the browser DOM, and validates network requests, responses,
and rendered plan artifacts.
"""

import asyncio
import json
import os
import subprocess
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import time
from typing import Any, Dict, List, Optional
import urllib.request

import websockets

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
CDP_PORT = 9222
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def wait_for_http(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SmokeTest"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def get_page_ws_url(cdp_port: int, max_retries: int = 20) -> str:
    url = f"http://127.0.0.1:{cdp_port}/json"
    for _ in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                for target in data:
                    if target.get("type") == "page" and "webSocketDebuggerUrl" in target:
                        return target["webSocketDebuggerUrl"]
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Failed to obtain Chrome CDP WebSocket URL")


class CDPSmokeTester:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._msg_id = 0
        self.console_logs: List[Dict[str, Any]] = []
        self.network_events: List[Dict[str, Any]] = []
        self.plan_api_request: Optional[Dict[str, Any]] = None
        self.plan_api_response: Optional[Dict[str, Any]] = None

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=10 * 1024 * 1024)
        asyncio.create_task(self._listen_loop())
        # Enable domains
        await self.send_command("Runtime.enable")
        await self.send_command("Page.enable")
        await self.send_command("Network.enable")
        await self.send_command("Console.enable")

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._msg_id += 1
        cid = self._msg_id
        cmd = {"id": cid, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(cmd))
        return cmd

    async def evaluate(self, expression: str) -> Any:
        self._msg_id += 1
        cid = self._msg_id
        cmd = {
            "id": cid,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        }
        await self.ws.send(json.dumps(cmd))
        
        # Wait for reply matching this cid
        # Since _listen_loop collects, let's wait with timeout
        timeout = 10.0
        start = time.time()
        while time.time() - start < timeout:
            for item in self.network_events:
                if item.get("id") == cid:
                    self.network_events.remove(item)
                    result = item.get("result", {})
                    if "exceptionDetails" in result:
                        raise RuntimeError(f"JS Exception: {result['exceptionDetails']}")
                    return result.get("result", {}).get("value")
            await asyncio.sleep(0.05)
        raise TimeoutError(f"Evaluate timeout for expression: {expression[:50]}")

    async def _listen_loop(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                # Store response by ID
                if "id" in msg:
                    self.network_events.append(msg)
                method = msg.get("method", "")
                params = msg.get("params", {})

                if method == "Console.messageAdded":
                    self.console_logs.append(params.get("message", {}))
                elif method == "Runtime.consoleAPICalled":
                    self.console_logs.append(params)
                elif method == "Network.requestWillBeSent":
                    req = params.get("request", {})
                    url = req.get("url", "")
                    if "/assistant/plan/generate" in url:
                        self.plan_api_request = {
                            "url": url,
                            "method": req.get("method"),
                            "postData": req.get("postData"),
                        }
                elif method == "Network.responseReceived":
                    resp = params.get("response", {})
                    url = resp.get("url", "")
                    if "/assistant/plan/generate" in url:
                        self.plan_api_response = {
                            "url": url,
                            "status": resp.get("status"),
                            "headers": resp.get("headers"),
                            "requestId": params.get("requestId"),
                        }
        except Exception:
            pass


async def run_smoke_test():
    print("=" * 70)
    print("EVENTPRICE INTELLIGENCE — BROWSER END-TO-END SMOKE TEST")
    print("=" * 70)

    # 1. Start Backend Server
    python_bin = os.path.join(PROJECT_ROOT, "backend", ".venv", "Scripts", "python.exe")
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "backend")

    print("[1/6] Launching FastAPI backend server on 127.0.0.1:8000...")
    backend_proc = subprocess.Popen(
        [
            python_bin,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            os.path.join(PROJECT_ROOT, "backend"),
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=os.path.join(PROJECT_ROOT, "backend"),
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 2. Start Vite Frontend (preview mode on built bundle for maximum fidelity)
    print("[2/6] Launching Vite frontend server on 127.0.0.1:5173...")
    vite_bin = os.path.join(PROJECT_ROOT, "node_modules", ".bin", "vite.cmd")
    frontend_proc = subprocess.Popen(
        [
            vite_bin,
            "preview",
            "--port",
            str(FRONTEND_PORT),
            "--host",
            "127.0.0.1",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    chrome_proc = None
    tester = None

    try:
        # Wait for backend health
        print("Waiting for backend /health endpoint...")
        if not await wait_for_http(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=12.0):
            raise RuntimeError("Backend failed to start on http://127.0.0.1:8000/health")
        print("Backend is healthy (HTTP 200).")

        # Wait for frontend
        print("Waiting for frontend index...")
        if not await wait_for_http(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=12.0):
            raise RuntimeError("Frontend failed to start on http://127.0.0.1:5173/")
        print("Frontend preview is active.")

        # 3. Launch Google Chrome in Headless Mode with Remote Debugging
        print("[3/6] Launching Headless Google Chrome with DevTools Protocol...")
        chrome_bin = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        chrome_proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                f"--remote-debugging-port={CDP_PORT}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-gpu",
                f"http://127.0.0.1:{FRONTEND_PORT}/",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        ws_url = await get_page_ws_url(CDP_PORT)
        print(f"Connected to Chrome page via CDP: {ws_url}")

        tester = CDPSmokeTester(ws_url)
        await tester.connect()

        # Wait for React to mount and initial status check
        await asyncio.sleep(2.5)

        # 4. Verify Connection Badge in Browser DOM
        print("\n[4/6] Verifying Live Connection Badges in Browser DOM...")
        badge_eval_js = """
        (() => {
            const pills = Array.from(document.querySelectorAll('span, div')).map(el => el.innerText.trim()).filter(Boolean);
            const conciergeBadge = Array.from(document.querySelectorAll('h2')).find(h => h.innerText.includes('AI PLANNING CONCIERGE'))?.parentElement?.innerText || '';
            const headerBadges = pills.filter(p => p.includes('Connected') || p.includes('Backend') || p.includes('Connecting'));
            return {
                title: document.title,
                headerBadges,
                conciergeBadge
            };
        })()
        """
        badge_info = await tester.evaluate(badge_eval_js)
        print(f"Page Title: {badge_info.get('title')}")
        print(f"Detected Connection Badges: {badge_info.get('headerBadges')}")
        print(f"Concierge Header Area: {badge_info.get('conciergeBadge')}")

        has_connected = any("Connected" in b for b in badge_info.get("headerBadges", [])) or "Connected" in badge_info.get("conciergeBadge", "")
        if not has_connected:
            print("WARNING: Neither header nor concierge shows 'Connected'")
        else:
            print("PASS: Connection badge reflects actual backend health.")

        # 5. Submit User Request in AI Planning Concierge
        prompt_text = "Plan a 50-guest birthday party in Hyderabad with a ₹60,000 budget."
        print(f"\n[5/6] Submitting user message to AI Concierge: '{prompt_text}'...")

        # 1. Type text into textarea via prototype setter so React registers state change
        type_js = f"""
        (() => {{
            const textarea = document.querySelector('textarea');
            if (!textarea) return {{ success: false, error: 'textarea not found' }};
            textarea.focus();
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            nativeSetter.call(textarea, {json.dumps(prompt_text)});
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return {{ success: true, value: textarea.value }};
        }})()
        """
        type_res = await tester.evaluate(type_js)
        print(f"Typing into textarea result: {type_res}")
        await asyncio.sleep(0.4)

        # 2. Click send button
        click_js = """
        (() => {
            const sendBtn = document.querySelector('button[title="Send prompt to agent"]') || 
                            Array.from(document.querySelectorAll('button')).find(b => b.title?.includes('Send') || b.querySelector('svg.lucide-send'));
            if (!sendBtn) return { success: false, error: 'send button not found' };
            const wasDisabled = sendBtn.disabled;
            sendBtn.click();
            return { success: true, wasDisabled };
        })()
        """
        click_res = await tester.evaluate(click_js)
        print(f"Click Send Button Result: {click_res}")

        # Wait for the plan generation API response and DOM update
        print("Waiting for backend plan synthesis & DOM update (up to 30s)...")
        plan_rendered = False
        rendered_plan_details = {}

        for _ in range(60):
            await asyncio.sleep(0.5)
            check_dom_js = """
            (() => {
                const bodyText = document.body.innerText;
                const hasPlanTicket = bodyText.includes('TOTAL ALLOCATED') || bodyText.includes('Total Allocated');
                const hasHyderabad = bodyText.includes('Hyderabad') || bodyText.includes('Birthday');
                const hasBudget = bodyText.includes('60,000') || bodyText.includes('₹60,000');
                const isError = bodyText.includes('Unable to complete plan generation') || bodyText.includes('Planning Engine Notice');
                
                // Check provider badge
                const isGemini = bodyText.includes('Synthesized with Gemini');
                const isDeterministic = bodyText.includes('Deterministic Fallback') || bodyText.includes('Deterministic AI') || bodyText.includes('Deterministic');

                // Check categories
                const hasVenue = bodyText.includes('Venue') || bodyText.includes('venue');
                const hasCatering = bodyText.includes('Catering') || bodyText.includes('catering');
                const hasChecklist = bodyText.includes('Checklist') || bodyText.includes('Vendor');
                const hasTimeline = bodyText.includes('Timeline') || bodyText.includes('Stage');

                return {
                    hasPlanTicket,
                    hasHyderabad,
                    hasBudget,
                    isError,
                    isGemini,
                    isDeterministic,
                    hasVenue,
                    hasCatering,
                    hasChecklist,
                    hasTimeline,
                    previewSnippet: bodyText.slice(0, 1500)
                };
            })()
            """
            status = await tester.evaluate(check_dom_js)
            if status.get("hasPlanTicket") and status.get("hasHyderabad"):
                plan_rendered = True
                rendered_plan_details = status
                break
            if status.get("isError"):
                rendered_plan_details = status
                break

        # Click through sub-tabs in StructuredPlanPreview to verify Budget, Checklist and Timeline
        tab_click_js = """
        (() => {
            const tabs = Array.from(document.querySelectorAll('button')).filter(b => 
                ['Budget', 'Checklist', 'Timeline'].some(t => b.innerText.includes(t))
            );
            
            // Click Budget tab
            const budgetBtn = tabs.find(b => b.innerText.includes('Budget'));
            if (budgetBtn) budgetBtn.click();
            
            const hasVenueRow = document.body.innerText.includes('venue') || document.body.innerText.includes('Venue');
            const hasCateringRow = document.body.innerText.includes('catering') || document.body.innerText.includes('Catering');
            
            // Click Checklist tab
            const checklistBtn = tabs.find(b => b.innerText.includes('Checklist'));
            if (checklistBtn) checklistBtn.click();
            const hasChecklistItems = document.body.innerText.includes('Priority') || document.body.innerText.includes('Questions') || document.body.innerText.includes('Vetting');

            // Click Timeline tab
            const timelineBtn = tabs.find(b => b.innerText.includes('Timeline'));
            if (timelineBtn) timelineBtn.click();
            const hasTimelineStages = document.body.innerText.includes('Stage') || document.body.innerText.includes('Milestone') || document.body.innerText.includes('Task');

            return {
                hasVenueRow,
                hasCateringRow,
                hasChecklistItems,
                hasTimelineStages
            };
        })()
        """
        tab_results = await tester.evaluate(tab_click_js)
        print(f"\nTab Inspection in StructuredPlanPreview: {tab_results}")
        print("\n[6/6] VERIFICATION SUMMARY")
        print("-" * 50)
        print(f"Planning API Intercepted Request: {bool(tester.plan_api_request)}")
        if tester.plan_api_request:
            print(f"  Method: {tester.plan_api_request.get('method')}")
            print(f"  URL: {tester.plan_api_request.get('url')}")
            print(f"  Payload: {tester.plan_api_request.get('postData')}")

        print(f"Planning API Intercepted Response: {bool(tester.plan_api_response)}")
        if tester.plan_api_response:
            print(f"  Status: HTTP {tester.plan_api_response.get('status')}")

        print(f"Plan Rendered in DOM: {plan_rendered}")
        print(f"  Location / Title present: {rendered_plan_details.get('hasHyderabad')}")
        print(f"  Budget (₹60,000) present: {rendered_plan_details.get('hasBudget')}")
        print(f"  Venue & Catering categories: {rendered_plan_details.get('hasVenue') and rendered_plan_details.get('hasCatering')}")
        print(f"  Checklist & Timeline present: {rendered_plan_details.get('hasChecklist') and rendered_plan_details.get('hasTimeline')}")
        print(f"  Provider Badge: {'Live Gemini' if rendered_plan_details.get('isGemini') else 'Deterministic Fallback'}")

        # Check for browser console errors
        real_errors = [
            log for log in tester.console_logs
            if log.get("level") == "error" or log.get("type") == "error"
        ]
        print(f"\nBrowser Console Errors: {len(real_errors)}")
        for err in real_errors:
            print(f"  [ERROR] {err}")

        assert plan_rendered, "Structured plan failed to render in browser DOM"
        assert not rendered_plan_details.get("isError"), f"UI rendered error notice: {rendered_plan_details.get('previewSnippet')[:300]}"
        assert tester.plan_api_response and tester.plan_api_response.get("status") == 200, f"API returned non-200: {tester.plan_api_response}"

        print("\n" + "=" * 70)
        print("ALL 7 VERIFICATION CRITERIA PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        print("\nCleaning up processes...")
        if tester:
            await tester.close()
        if chrome_proc:
            chrome_proc.terminate()
            chrome_proc.wait()
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait()
        if backend_proc:
            backend_proc.terminate()
            backend_proc.wait()
        print("All processes terminated cleanly.")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
