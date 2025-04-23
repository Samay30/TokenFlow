import requests
import argparse
import json
import sys
import csv
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from urllib.parse import unquote_plus

class Service:
    def __init__(self, name, auth_url, client_id, client_secret, token_url, redirect_uri, userinfo_url):
        self.name = name
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.userinfo_url = userinfo_url

def get_auth_code_via_playwright(auth_url, redirect_uri, context):
    page = context.new_page()
    auth_code = None

    def intercept_post(route, request):
        nonlocal auth_code
        if request.method == "POST" and redirect_uri in request.url:
            post_data = request.post_data
            if post_data:
                parsed_data = dict(pair.split('=') for pair in post_data.split('&') if '=' in pair)
                if 'code' in parsed_data:
                    auth_code = unquote_plus(parsed_data['code'])
                    print(f"[✅] Extracted auth code from POST payload: {auth_code}")
        route.continue_()

    page.route("**", intercept_post)

    print(f"[🌐] Navigating to auth URL: {auth_url}")
    page.goto(auth_url)
    print("[✍️] Please complete login in the browser window...")

    start_time = time.time()
    while time.time() - start_time < 120:
        current_url = page.url

        if "shib.unl.edu" in current_url and "shib-qa.unl.edu" not in current_url:
            fixed_url = current_url.replace("shib.unl.edu", "shib-qa.unl.edu")
            print(f"[🔧] Detected stale prod URL. Fixing to QA: {fixed_url}")
            try:
                page.goto(fixed_url)
                continue
            except Exception as e:
                print(f"[⚠️] Failed to navigate to QA URL: {e}")

        if auth_code:
            break

        print(f"[⏳] Waiting... Current URL: {current_url}")
        page.wait_for_timeout(1000)

    page.close()

    if not auth_code:
        print("[❌] Failed to obtain authorization code")
        raise Exception("Authorization code not found")

    return auth_code

def exchange_code_for_token(auth_code, client_id, client_secret, token_url, redirect_uri):
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    response = requests.post(token_url, data=data, headers=headers)
    print(f"[📥] Response ({response.status_code}): {response.text}")

    response.raise_for_status()
    return response.json()

def get_user_info(access_token, userinfo_url):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(userinfo_url, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="OIDC Authentication Multi-Service Flow")
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    parser.add_argument('--output', default='tokenflow_results.csv', help='Path to save CSV results')
    parser.add_argument('services', nargs='+', metavar='SERVICE', help='Multiple service definitions as JSON strings')
    args = parser.parse_args()

    services = []
    for svc_raw in args.services:
        svc_dict = json.loads(svc_raw)
        svc = Service(
            name=svc_dict.get('name', 'Unnamed Service'),
            auth_url=svc_dict['auth_url'],
            client_id=svc_dict['client_id'],
            client_secret=svc_dict['client_secret'],
            token_url=svc_dict['token_url'],
            redirect_uri=svc_dict['redirect_uri'],
            userinfo_url=svc_dict['userinfo_url']
        )
        services.append(svc)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        for i, svc in enumerate(services):
            print(f"\n🔁 Starting test for: {svc.name}")
            result = {
                "Service Name": svc.name,
                "Auth Code Captured": "No",
                "Token Exchange": "Failed",
                "UserInfo": "N/A",
                "Timestamp": datetime.now().isoformat()
            }
            try:
                if i == 0:
                    print("[🔓] Initiating login for first service")
                else:
                    print("[🔁] Reusing session to open next auth flow")

                auth_code = get_auth_code_via_playwright(svc.auth_url, svc.redirect_uri, context)
                result["Auth Code Captured"] = "Yes"
                print(f"[🔑] Authorization code: {auth_code}")

                tokens = exchange_code_for_token(
                    auth_code,
                    svc.client_id,
                    svc.client_secret,
                    svc.token_url,
                    svc.redirect_uri
                )
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
                print(f"[❌] Failed for {svc.name}: {e}")
                result["Error"] = str(e)

            results.append(result)

        context.close()
        browser.close()

    # Write CSV
    keys = ["Service Name", "Auth Code Captured", "Token Exchange", "UserInfo", "Timestamp", "Error"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"\n✅ Results saved to {args.output}")

if __name__ == '__main__':
    main()
