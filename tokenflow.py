import requests
import argparse
import json
import sys
import csv
import time
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import unquote_plus, urlparse

SERVICE_MAP_FILE = Path(".tokenflow_services.json")

# Hardcoded credentials for QA environment
QA_USERNAME = "76423153"
QA_PASSWORD = "TokenFlow1234"

class Service:
    def __init__(self, name, auth_url, client_id, client_secret, token_url, redirect_uri, userinfo_url):
        self.name = name
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.userinfo_url = userinfo_url

def save_service_map(service_map):
    with open(SERVICE_MAP_FILE, "w") as f:
        json.dump(service_map, f, indent=2)

def load_service_map():
    if SERVICE_MAP_FILE.exists():
        with open(SERVICE_MAP_FILE) as f:
            return json.load(f)
    return {}

def add_service_to_map(name, metadata_url):
    service_map = load_service_map()
    service_map[name] = metadata_url
    save_service_map(service_map)
    print(f"✅ Added service '{name}' to local map.")

def parse_oidc_metadata(xml_content):
    ns = {
        "md": "urn:oasis:names:tc:SAML:2.0:metadata",
        "oidcmd": "urn:mace:shibboleth:metadata:oidc:1.0",
        "ds": "http://www.w3.org/2000/09/xmldsig#"
    }
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"[❌] XML parsing error: {e}")
        # Save problematic XML for debugging
        with open("bad_metadata.xml", "w") as f:
            f.write(xml_content)
        raise
    root = ET.fromstring(xml_content)
    client_id = root.find(".//oidcmd:ClientSecretKeyReference", ns).text
    redirect_uri = root.find(".//md:AssertionConsumerService", ns).attrib["Location"]
    auth_url = "https://fedt.nebraska.edu/idp/profile/oidc/authorize"
    token_url = "https://shib-qa.unl.edu/idp/profile/oidc/token"
    userinfo_url = "https://shib-qa.unl.edu/idp/profile/oidc/userinfo"
    return client_id, redirect_uri, auth_url, token_url, userinfo_url

def build_services_from_names(service_names):
    services = []
    service_map = load_service_map()
    for name in service_names:
        if name not in service_map:
            print(f"[❌] Service '{name}' not found in local map. Use --add-service to add it.")
            continue
        xml_url = service_map[name]
        try:
            response = requests.get(xml_url, timeout=10)
            response.raise_for_status()
            client_id, redirect_uri, auth_url, token_url, userinfo_url = parse_oidc_metadata(response.text)
            
            # Validate redirect URI
            parsed_uri = urlparse(redirect_uri)
            if not parsed_uri.scheme or not parsed_uri.netloc:
                print(f"[⚠️] Invalid redirect URI for '{name}': {redirect_uri}")
                redirect_uri = "https://default.unl.edu/fallback"  # Provide a fallback
            
            secret_env_key = name.upper() + "_SECRET"
            client_secret = os.environ.get(secret_env_key)
            if not client_secret:
                raise Exception(f"Environment variable '{secret_env_key}' not set.")
            
            # Build auth URL with proper encoding
            params = {
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'scope': 'openid email profile',
                'state': '1234',
                'response_type': 'code+id_token',
                'response_mode': 'form_post',
                'nonce': '4321'
            }
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_auth_url = f"{auth_url}?{query_string}"
            
            svc = Service(
                name=name,
                auth_url=full_auth_url,
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                redirect_uri=redirect_uri,
                userinfo_url=userinfo_url
            )
            services.append(svc)
        except Exception as e:
            print(f"[⚠️] Failed to fetch metadata for '{name}': {e}")
    return services

def get_auth_code_via_playwright(svc, context):
    auth_url = svc.auth_url
    redirect_uri = svc.redirect_uri
    page = context.new_page()
    auth_code = None
    critical_error = None

    # Handle JavaScript errors
    def handle_page_error(error):
        nonlocal critical_error
        critical_error = f"Page error: {error}"
        print(f"[❌] {critical_error}")

    # Handle network failures
    def handle_network_failure(request):
        nonlocal critical_error
        if request.failure and not critical_error:
            # Only set if we don't have an error already
            critical_error = f"Network failure: {request.failure} - URL: {request.url}"
            print(f"[🌐] {critical_error}")

    page.on("pageerror", handle_page_error)
    page.on("requestfailed", handle_network_failure)

    def intercept_post(route, request):
        nonlocal auth_code
        if request.method == "POST" and redirect_uri in request.url:
            try:
                post_data = request.post_data
                if post_data:
                    # Parse form data
                    parsed_data = {}
                    for pair in post_data.split('&'):
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            parsed_data[unquote_plus(key)] = unquote_plus(value)
                    
                    if 'code' in parsed_data:
                        auth_code = parsed_data['code']
                        print(f"[✅] Extracted auth code from POST payload: {auth_code}")
            except Exception as e:
                print(f"[⚠️] Error parsing POST data: {e}")
        route.continue_()

    page.route("**", intercept_post)

    print(f"[🌐] Starting authentication for: {svc.name}")
    print(f"[🔗] Auth URL: {auth_url[:100]}...")  # Truncate long URLs

    try:
        # Attempt navigation with timeout handling
        page.goto(auth_url, timeout=60000, wait_until="domcontentloaded")
        print(f"[🌐] Initial navigation completed to: {page.url[:100]}...")
        
        # Check if we're on an error page
        if "error" in page.url.lower() or "chrome-error" in page.url:
            critical_error = f"Browser error page encountered: {page.url}"
            print(f"[❌] {critical_error}")
        
        # Handle IdP login with hardcoded credentials
        if "fedt.nebraska.edu" in page.url and "authorize" in page.url.lower():
            print("[🔐] Detected login page, automatically logging in...")
            page.fill("#username", QA_USERNAME)
            page.fill("#password", QA_PASSWORD)
            page.click("#Login")
            page.wait_for_timeout(3000)  # Wait for login processing
            
        # Wait for redirect to occur
        start_time = time.time()
        while time.time() - start_time < 120:  # 2 minute timeout
            if auth_code or critical_error:
                break
                
            # Check for unexpected pages
            current_url = page.url
            if "error" in current_url.lower() or "chrome-error" in current_url:
                critical_error = f"Unexpected error page: {current_url}"
                break
                
            print(f"[⏳] Waiting for redirect... Current URL: {current_url[:100]}...")
            page.wait_for_timeout(2000)
            
    except Exception as e:
        critical_error = f"Navigation error: {str(e)}"
        print(f"[❌] {critical_error}")

    # Final diagnostics
    if auth_code:
        print(f"[✅] Successfully obtained auth code for {svc.name}")
    else:
        screenshot_path = f"error_{svc.name}_{int(time.time())}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[📸] Saved screenshot to {screenshot_path}")
        
        content_path = f"page_{svc.name}_{int(time.time())}.html"
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"[📝] Saved page content to {content_path}")
        
        if not critical_error:
            critical_error = "Authorization code not received within timeout period"

    page.close()
    
    if critical_error:
        raise Exception(critical_error)
        
    return auth_code

def exchange_code_for_token(auth_code, svc):
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': svc.redirect_uri,
        'client_id': svc.client_id,
        'client_secret': svc.client_secret
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        print(f"[🔁] Exchanging code for token at: {svc.token_url}")
        response = requests.post(svc.token_url, data=data, headers=headers, timeout=15)
        print(f"[📥] Token response ({response.status_code}): {response.text[:200]}...")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[❌] Token exchange failed: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"[🚫] Server response: {e.response.text[:500]}")
        raise

def get_user_info(access_token, userinfo_url):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(userinfo_url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="TokenFlow - Automated OIDC QA Testing Tool")
    parser.add_argument('--add-service', nargs=2, metavar=('NAME', 'METADATA_URL'), help='Add a new service')
    parser.add_argument('--list-services', action='store_true', help='List available services')
    parser.add_argument('--run', nargs='+', metavar='SERVICE_NAME', help='Run OIDC test on specified services')
    parser.add_argument('--output', default='tokenflow_results.csv', help='CSV file to write results to')
    parser.add_argument('--json', action='store_true', help='Print userinfo in JSON format')
    args = parser.parse_args()

    if args.add_service:
        name, url = args.add_service
        add_service_to_map(name, url)
        return

    if args.list_services:
        service_map = load_service_map()
        print("\nAvailable services:")
        for k, v in service_map.items():
            print(f"- {k}: {v}")
        return

    if args.run:
        services = build_services_from_names(args.run)
    else:
        print("[❌] No services specified. Use --run or --add-service.")
        return

    results = []
    with sync_playwright() as p:
        # Configure browser with enhanced settings
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--no-sandbox",
                "--single-process",
                "--window-size=1280,1024"
            ],
            timeout=60000
        )
        
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1024},
            java_script_enabled=True,
            ignore_https_errors=False
        )

        for svc in services:
            print(f"\n🔁 Starting test for: {svc.name}")
            result = {
                "Service Name": svc.name,
                "Auth Code Captured": "No",
                "Token Exchange": "Failed",
                "UserInfo": "N/A",
                "Timestamp": datetime.now().isoformat()
            }
            try:
                # Pre-check service URLs
                print(f"[🔍] Verifying service endpoints...")
                for url in [svc.auth_url, svc.token_url, svc.userinfo_url]:
                    try:
                        response = requests.head(url, timeout=5, allow_redirects=True)
                        print(f"  - {url[:60]}...: HTTP {response.status_code}")
                        if response.status_code >= 400:
                            print(f"    [⚠️] WARNING: Endpoint returned {response.status_code}")
                    except Exception as e:
                        print(f"  - {url[:60]}...: ERROR ({str(e)})")
                
                auth_code = get_auth_code_via_playwright(svc, context)
                result["Auth Code Captured"] = "Yes"

                tokens = exchange_code_for_token(auth_code, svc)
                result["Token Exchange"] = "Success"

                userinfo = get_user_info(tokens['access_token'], svc.userinfo_url)
                result["UserInfo"] = userinfo.get("email") or userinfo.get("sub") or "Retrieved"

                if args.json:
                    print(json.dumps({"service": svc.name, "userinfo": userinfo}, indent=2))
                else:
                    print("\n[👤] User Information:")
                    for key, value in userinfo.items():
                        print(f"  {key}: {value}")

            except Exception as e:
                print(f"[❌] Critical failure for {svc.name}: {e}")
                result["Error"] = str(e)
                # Skip further tests for this service
                results.append(result)
                continue

            results.append(result)

        context.close()
        browser.close()

    keys = ["Service Name", "Auth Code Captured", "Token Exchange", "UserInfo", "Timestamp", "Error"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\n✅ Results saved to {args.output}")

if __name__ == '__main__':
    main()