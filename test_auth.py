import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from fpl_agent.data.fpl_api_client import FPLAPIClient

cookie = os.environ.get('FPL_COOKIE')
token = os.environ.get('FPL_ACCESS_TOKEN')

print(f"Cookie found: {bool(cookie)}")
print(f"Token found: {bool(token)}")

client = FPLAPIClient(cookie_string=cookie, access_token=token)
success = client.login()

if success:
    print(f"✅ Authentication successful! Team ID: {client.team_id}")
    team_data = client.get_my_team()
    if team_data:
        print(f"✅ Successfully fetched your private team data!")
        bank = team_data.get('transfers', {}).get('bank', 0) / 10
        print(f"   Current Bank: £{bank}m")
        
        print("\n🧪 Testing Sync by updating your Vice Captain...")
        picks = team_data.get('picks', [])
        
        if picks:
            # Shift VC to the first bench player for testing
            for p in picks:
                p['is_vice_captain'] = False
            picks[11]['is_vice_captain'] = True
            
            # Use the client to set the lineup
            sync_success = client.set_lineup(picks)
            
            if sync_success:
                print("✅ IT WORKS! Your FPL lineup was successfully updated on the official website.")
            else:
                print("❌ FAILED to sync lineup to FPL.")
        else:
            print("❌ No picks found in team data.")
else:
    print("❌ Authentication failed.")
