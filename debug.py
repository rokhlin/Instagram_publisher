"""
MemoryNMore Diagnostic & Debug Suite
Tests all components:
1. Environment & Configuration settings
2. Telegram Bot API Connectivity & Token
3. Instagram / Meta Graph API Credentials, Account Type & Publishing Limit
4. Google Gemini AI API Key & Generation
5. Storage Service (R2 / S3 / Local) Upload & Public URL Reachability
"""

import sys
import os
import io
import asyncio
import logging
from typing import Dict, Any, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiohttp
from PIL import Image

try:
    from src.config import settings
    from src.services.storage_service import storage_service
    from src.services.ai_service import ai_service
except ImportError as e:
    print(f"\033[91m[CRITICAL] Failed to import project modules: {e}\033[0m")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def mask_secret(value: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    if not value:
        return "[NOT SET]"
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}...{value[-visible_suffix:]} (len: {len(value)})"


def print_section(title: str):
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}")


def print_status(component: str, ok: bool, message: str, warn: bool = False):
    if ok:
        badge = f"{GREEN}[PASS]{RESET}"
    elif warn:
        badge = f"{YELLOW}[WARN]{RESET}"
    else:
        badge = f"{RED}[FAIL]{RESET}"
    print(f" {badge} {BOLD}{component}:{RESET} {message}")


async def test_config() -> Tuple[bool, str]:
    print_section("1. Environment & Configuration Check")
    
    print(f"  • STORAGE_TYPE:             {BOLD}{settings.STORAGE_TYPE}{RESET}")
    print(f"  • BOT_TOKEN:                {mask_secret(settings.BOT_TOKEN, 6, 4)}")
    print(f"  • ALLOWED_USER_IDS:         {settings.ALLOWED_USER_IDS or '[ALL USERS ALLOWED]'}")
    print(f"  • IG_USER_ID:               {settings.IG_USER_ID or '[NOT SET]'}")
    print(f"  • IG_ACCESS_TOKEN:          {mask_secret(settings.IG_ACCESS_TOKEN, 8, 6)}")
    print(f"  • IG_GRAPH_API_VERSION:     {settings.IG_GRAPH_API_VERSION}")
    print(f"  • GEMINI_API_KEY:           {mask_secret(settings.GEMINI_API_KEY, 4, 4)}")

    if settings.STORAGE_TYPE.lower() == "r2":
        print(f"  • R2_ACCOUNT_ID:            {mask_secret(settings.R2_ACCOUNT_ID, 4, 4)}")
        print(f"  • R2_ACCESS_KEY_ID:         {mask_secret(settings.R2_ACCESS_KEY_ID, 4, 4)}")
        print(f"  • R2_SECRET_ACCESS_KEY:     {mask_secret(settings.R2_SECRET_ACCESS_KEY, 4, 4)}")
        print(f"  • R2_BUCKET_NAME:           {settings.R2_BUCKET_NAME or '[NOT SET]'}")
        print(f"  • R2_PUBLIC_DOMAIN:         {settings.R2_PUBLIC_DOMAIN or '[NOT SET]'}")
    elif settings.STORAGE_TYPE.lower() == "s3":
        print(f"  • S3_ENDPOINT_URL:          {settings.S3_ENDPOINT_URL or '[AWS DEFAULT]'}")
        print(f"  • S3_ACCESS_KEY_ID:         {mask_secret(settings.S3_ACCESS_KEY_ID, 4, 4)}")
        print(f"  • S3_SECRET_ACCESS_KEY:     {mask_secret(settings.S3_SECRET_ACCESS_KEY, 4, 4)}")
        print(f"  • S3_BUCKET_NAME:           {settings.S3_BUCKET_NAME or '[NOT SET]'}")
        print(f"  • S3_PUBLIC_DOMAIN:         {settings.S3_PUBLIC_DOMAIN or '[NOT SET]'}")
    else:
        print(f"  • LOCAL_STORAGE_DIR:        {settings.LOCAL_STORAGE_DIR}")
        print(f"  • LOCAL_PUBLIC_BASE_URL:    {settings.LOCAL_PUBLIC_BASE_URL or '[NOT SET]'}")
        print(f"  • LOCAL_SERVER_ENABLED:     {settings.LOCAL_SERVER_ENABLED}")
        print(f"  • LOCAL_SERVER_PORT:        {settings.LOCAL_SERVER_PORT}")

    # Validation - only checks required common variables and active STORAGE_TYPE variables
    missing_vars = settings.validate_required_config()
    if missing_vars:
        msg = f"Missing required variables for active mode ({settings.STORAGE_TYPE}): {', '.join(missing_vars)}"
        print_status("Config Validation", False, msg)
        return False, msg

    print_status("Config Validation", True, f"All required environment variables for active mode ({settings.STORAGE_TYPE}) are populated.")
    return True, "OK"


async def test_telegram_bot() -> Tuple[bool, str]:
    print_section("2. Telegram Bot API Connectivity")
    if not settings.TELEGRAM_ENABLED or not settings.BOT_TOKEN:
        msg = "Telegram Bot is disabled or BOT_TOKEN not configured (Optional)"
        print_status("Telegram Bot", True, msg, warn=True)
        return True, "Disabled (Optional)"

    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getMe"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if resp.status == 200 and data.get("ok"):
                    bot_info = data.get("result", {})
                    username = bot_info.get("username", "Unknown")
                    first_name = bot_info.get("first_name", "")
                    bot_id = bot_info.get("id", "")
                    msg = f"Connected as @{username} (ID: {bot_id}, Name: '{first_name}')"
                    print_status("Telegram Bot", True, msg)
                    return True, msg
                else:
                    description = data.get("description", str(data))
                    msg = f"Telegram API error ({resp.status}): {description}"
                    print_status("Telegram Bot", False, msg)
                    return False, msg
    except Exception as e:
        msg = f"Failed to connect to api.telegram.org: {e}"
        print_status("Telegram Bot", False, msg)
        return False, msg


async def test_instagram_graph_api() -> Tuple[bool, str]:
    print_section("3. Instagram Graph API Verification")
    if not settings.IG_USER_ID or not settings.IG_ACCESS_TOKEN:
        print_status("Instagram API", False, "IG_USER_ID or IG_ACCESS_TOKEN is missing")
        return False, "Credentials missing"

    base_url = f"https://graph.facebook.com/{settings.IG_GRAPH_API_VERSION}"
    account_url = f"{base_url}/{settings.IG_USER_ID}"
    params = {
        "fields": "id,username,name",
        "access_token": settings.IG_ACCESS_TOKEN
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            # 1. Fetch Account Details
            async with session.get(account_url, params=params) as resp:
                data = await resp.json()
                if resp.status != 200 or "id" not in data:
                    err = data.get("error", {}).get("message", str(data))
                    code = data.get("error", {}).get("code", "")
                    subcode = data.get("error", {}).get("error_subcode", "")
                    msg = f"Graph API Error (Code {code}/{subcode}): {err}"
                    print_status("Account Verification", False, msg)
                    return False, msg

                username = data.get("username", "N/A")
                name = data.get("name", "N/A")
                print_status(
                    "Account Verification", 
                    True, 
                    f"Connected to Instagram Account: @{username} ({name})"
                )

            # 2. Check Content Publishing Limit (Quota)
            limit_url = f"{base_url}/{settings.IG_USER_ID}/content_publishing_limit"
            limit_params = {
                "fields": "quota_usage,config",
                "access_token": settings.IG_ACCESS_TOKEN
            }
            async with session.get(limit_url, params=limit_params) as resp:
                limit_data = await resp.json()
                if resp.status == 200 and "data" in limit_data and limit_data["data"]:
                    quota = limit_data["data"][0]
                    quota_usage = quota.get("quota_usage", 0)
                    quota_total = quota.get("config", {}).get("quota_total", 50)
                    print_status(
                        "Publishing Quota", 
                        True, 
                        f"Daily Posts Used: {quota_usage}/{quota_total}"
                    )
                else:
                    print_status("Publishing Quota", True, "Quota endpoint checked.", warn=True)

            return True, f"@{username} verified successfully"

    except Exception as e:
        msg = f"Network exception reaching graph.facebook.com: {e}"
        print_status("Instagram API", False, msg)
        return False, msg


async def test_gemini_ai() -> Tuple[bool, str]:
    print_section("4. Google Gemini AI Service")
    if not settings.GEMINI_API_KEY:
        print_status("Gemini AI", False, "GEMINI_API_KEY not configured. Falling back to template captions.", warn=True)
        return True, "Fallback mode (No API Key)"

    try:
        caption = await ai_service.generate_caption(instructions="Debug test: beautiful sunrise in mountains", post_format="FEED_PORTRAIT")
        if caption and len(caption) > 20 and not caption.startswith("Rediscovering the world"):
            preview = caption.split("\n")[0][:60]
            print_status("Gemini AI", True, f"Caption generation active (Model: gemini-3.7-flash). Preview: '{preview}...'")
            return True, "OK"
        elif caption:
            print_status("Gemini AI", False, "Generated default fallback caption instead of Gemini response. Check API key/quotas.", warn=True)
            return False, "Fallback triggered"
        else:
            print_status("Gemini AI", False, "Empty response from Gemini service.")
            return False, "Empty response"
    except Exception as e:
        msg = f"Gemini API error: {e}"
        print_status("Gemini AI", False, msg)
        return False, msg


async def test_storage_and_reachability() -> Tuple[bool, str]:
    print_section("5. Storage & Public URL Reachability Check")
    
    # 1. Create a 100x100 RGB JPEG test image in memory
    img = Image.new("RGB", (100, 100), color=(70, 130, 180))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    image_bytes = buffer.getvalue()
    test_filename = f"debug_health_test_{os.getpid()}.jpg"

    public_url = None
    try:
        # 2. Upload using configured storage service
        public_url = await storage_service.upload_image(image_bytes, filename=test_filename)
        print_status("Storage Upload", True, f"Uploaded test file '{test_filename}' -> {public_url}")
    except Exception as e:
        msg = f"Storage upload failed: {e}"
        print_status("Storage Upload", False, msg)
        return False, msg

    # 3. Test HTTP reachability from external perspective
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(public_url) as resp:
                content_type = resp.headers.get("Content-Type", "")
                content_len = resp.headers.get("Content-Length", "")
                if resp.status == 200 and "image" in content_type.lower():
                    msg = f"Public URL is accessible! HTTP 200 (Type: {content_type}, Size: {len(await resp.read())} bytes)"
                    print_status("Public URL Reachability", True, msg)
                elif resp.status == 200:
                    msg = f"Public URL returned HTTP 200 but unexpected Content-Type: {content_type}"
                    print_status("Public URL Reachability", False, msg, warn=True)
                else:
                    msg = f"Public URL returned HTTP {resp.status}. Meta Graph API will NOT be able to download this image!"
                    print_status("Public URL Reachability", False, msg)
                    return False, msg
    except Exception as e:
        msg = f"Failed to fetch public URL ({public_url}): {e}"
        print_status("Public URL Reachability", False, msg)
        return False, msg

    # 4. Clean up test file from S3/R2 if possible
    if storage_service.s3_client and settings.s3_or_r2_bucket:
        try:
            storage_service.s3_client.delete_object(
                Bucket=settings.s3_or_r2_bucket,
                Key=test_filename
            )
            print_status("Cleanup", True, f"Cleaned up remote test object '{test_filename}' from bucket.")
        except Exception:
            pass

    # Clean up local file if created
    local_path = os.path.join(settings.LOCAL_STORAGE_DIR, test_filename)
    if os.path.exists(local_path):
        try:
            os.remove(local_path)
            print_status("Cleanup", True, f"Cleaned up local test file '{local_path}'.")
        except Exception:
            pass

    return True, "Storage and public URL verified"


async def test_whatsapp_connector() -> Tuple[bool, str]:
    print_section("6. WhatsApp Connector (whatsapp-web.js)")

    if not settings.WHATSAPP_ENABLED:
        msg = "WhatsApp integration is disabled (WHATSAPP_ENABLED=false)"
        print_status("WhatsApp Integration", True, msg, warn=True)
        return True, "Disabled (Optional)"

    connector_url = settings.WHATSAPP_CONNECTOR_URL.rstrip("/")
    status_url = f"{connector_url}/api/status"
    print(f"Testing WhatsApp Connector API at {CYAN}{status_url}{RESET}...")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(status_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    status = data.get("status", "UNKNOWN")
                    is_ready = data.get("is_ready", False)
                    has_qr = data.get("has_qr", False)
                    client_info = data.get("client_info") or {}

                    if is_ready:
                        phone = client_info.get("phone", "N/A")
                        name = client_info.get("name", "User")
                        msg = f"Connected as {name} (+{phone}) | Status: READY"
                        print_status("WhatsApp Client", True, msg)
                        return True, "Connected & Ready"
                    elif has_qr:
                        msg = f"Client is waiting for QR code scan. Open {connector_url}/qr to scan."
                        print_status("WhatsApp Client", True, msg, warn=True)
                        return True, "Awaiting QR Scan"
                    else:
                        msg = f"Connector is running. Current Status: {status}"
                        print_status("WhatsApp Client", True, msg, warn=True)
                        return True, f"Status: {status}"
                else:
                    msg = f"Connector returned HTTP {resp.status}"
                    print_status("WhatsApp Connector", False, msg)
                    return False, msg
    except Exception as e:
        msg = f"Cannot reach WhatsApp connector at {status_url} ({e}). Ensure the Node.js connector or docker service is running."
        print_status("WhatsApp Connector", False, msg, warn=True)
        return False, "Unreachable (Check if running)"


async def run_all_checks():
    print(f"\n{BOLD}{CYAN}================================================================{RESET}")
    print(f"{BOLD}{CYAN}      MemoryNMore Automated Diagnostic & Debug Suite           {RESET}")
    print(f"{BOLD}{CYAN}================================================================{RESET}")

    results = {}
    
    # 1. Config Check
    results["Config"] = await test_config()

    # 2. Telegram Bot Check
    results["Telegram"] = await test_telegram_bot()

    # 3. Instagram Graph API Check
    results["Instagram"] = await test_instagram_graph_api()

    # 4. Gemini AI Check
    results["Gemini AI"] = await test_gemini_ai()

    # 5. Storage & Public Reachability Check
    results["Storage"] = await test_storage_and_reachability()

    # 6. WhatsApp Connector Check (if enabled)
    if settings.WHATSAPP_ENABLED:
        results["WhatsApp"] = await test_whatsapp_connector()

    # Summary
    print_section("Summary & Overall Health")
    all_passed = True
    for name, (ok, note) in results.items():
        status_text = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        if name == "Gemini AI" and "Fallback" in note:
            status_text = f"{YELLOW}WARN (Fallback){RESET}"
        elif name == "WhatsApp" and ("Awaiting" in note or "Unreachable" in note):
            status_text = f"{YELLOW}WARN ({note}){RESET}"
        print(f"  • {name:<15}: {status_text} ({note})")
        if not ok and name not in ("Gemini AI", "WhatsApp"):
            all_passed = False

    print(f"\n{CYAN}{'-'*60}{RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}🎉 ALL PRIMARY SYSTEMS ARE OPERATIONAL & READY TO POST!{RESET}")
    else:
        print(f"{RED}{BOLD}⚠️ ONE OR MORE CHECKS FAILED. Please review the errors above.{RESET}")
    print(f"{CYAN}{'-'*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_all_checks())

