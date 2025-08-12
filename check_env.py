#!/usr/bin/env python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Check environment variables
print("Environment Variables Status:")
print("=" * 40)

freee_token = os.getenv('FREEE_ACCESS_TOKEN')
if freee_token and freee_token != 'your_freee_access_token_here':
    print("✓ FREEE_ACCESS_TOKEN: SET")
else:
    print("✗ FREEE_ACCESS_TOKEN: NOT SET")

company_id = os.getenv('FREEE_COMPANY_ID')
if company_id and company_id != '123456':
    print(f"✓ FREEE_COMPANY_ID: {company_id}")
else:
    print("✗ FREEE_COMPANY_ID: NOT SET")

claude_key = os.getenv('FREEE_CLAUDE_API_KEY')
if claude_key and claude_key != 'your_freee_claude_api_key_here':
    print("✓ FREEE_CLAUDE_API_KEY: SET")
else:
    print("✗ FREEE_CLAUDE_API_KEY: NOT SET")

slack_url = os.getenv('SLACK_WEBHOOK_URL')
if slack_url and 'hooks.slack.com' in slack_url:
    print("✓ SLACK_WEBHOOK_URL: SET")
else:
    print("✗ SLACK_WEBHOOK_URL: NOT SET (optional)")

dry_run = os.getenv('DRY_RUN', 'false')
print(f"\nDRY_RUN mode: {dry_run}")