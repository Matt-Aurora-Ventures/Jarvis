# This is /home/ubuntu/copri_app/src/integrations/trello_integration.py
import requests
import json

TRELLO_API_BASE_URL = "https://api.trello.com/1"

class TrelloIntegration:
    def __init__(self, api_key, token):
        self.api_key = api_key
        self.token = token
        self.auth_params = {
            "key": self.api_key,
            "token": self.token
        }

    def get_member_info(self):
        """Fetches information about the token owner."""
        url = f"{TRELLO_API_BASE_URL}/members/me"
        try:
            response = requests.get(url, params=self.auth_params)
            response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching member info from Trello: {e}")
            return None

    def get_boards(self):
        """Fetches all boards for the authenticated user."""
        url = f"{TRELLO_API_BASE_URL}/members/me/boards"
        params = {**self.auth_params, "filter": "open", "fields": "id,name,url"}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Trello boards: {e}")
            return []

    def get_lists_for_board(self, board_id):
        """Fetches all lists for a specific board."""
        url = f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists"
        params = {**self.auth_params, "cards": "open", "card_fields": "id,name,due,desc", "fields": "id,name"}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching lists for board {board_id}: {e}")
            return []

    def get_cards_for_list(self, list_id):
        """Fetches all cards for a specific list."""
        url = f"{TRELLO_API_BASE_URL}/lists/{list_id}/cards"
        params = {**self.auth_params, "fields": "id,name,desc,due,idList,idBoard,labels,url"}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching cards for list {list_id}: {e}")
            return []

    def create_card(self, id_list, name, desc=None, due=None, id_labels=None, url_source=None):
        """Creates a new card on a specific list."""
        url = f"{TRELLO_API_BASE_URL}/cards"
        payload = {
            **self.auth_params,
            "idList": id_list,
            "name": name,
        }
        if desc: payload["desc"] = desc
        if due: payload["due"] = due # ISO 8601 format or null
        if id_labels: payload["idLabels"] = ",".join(id_labels) # Comma-separated string of label IDs
        if url_source: payload["urlSource"] = url_source

        try:
            response = requests.post(url, json=payload) # Trello API often uses query params for POST too, but json for body is safer for complex data
            # Let's check Trello docs. For card creation, it's query parameters.
            response = requests.post(url, params=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating card \'{name}\' in list {id_list}: {e}")
            print(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None

# Example usage (for testing, would be called from a service or route)
# if __name__ == "__main__":
#     # IMPORTANT: Replace with your actual API key and token for testing
#     # You can get these from: https://trello.com/app-key
#     TEST_API_KEY = "YOUR_TRELLO_API_KEY"
#     TEST_TOKEN = "YOUR_TRELLO_TOKEN"

#     if TEST_API_KEY == "YOUR_TRELLO_API_KEY" or TEST_TOKEN == "YOUR_TRELLO_TOKEN":
#         print("Please replace YOUR_TRELLO_API_KEY and YOUR_TRELLO_TOKEN with your actual credentials to test.")
#     else:
#         trello_client = TrelloIntegration(api_key=TEST_API_KEY, token=TEST_TOKEN)
        
#         member_info = trello_client.get_member_info()
#         if member_info:
#             print(f"Authenticated as: {member_info.get('fullName', member_info.get('username'))}")

#         boards = trello_client.get_boards()
#         print(f"Found boards: {json.dumps(boards, indent=2)}")
#         if boards:
#             first_board_id = boards[0]["id"]
#             print(f"--- Fetching lists for board: {boards[0]['name']} ({first_board_id}) ---")
#             lists = trello_client.get_lists_for_board(first_board_id)
#             print(f"Found lists: {json.dumps(lists, indent=2)}")
#             if lists:
#                 first_list_id = lists[0]["id"]
#                 print(f"--- Fetching cards for list: {lists[0]['name']} ({first_list_id}) ---")
#                 cards = trello_client.get_cards_for_list(first_list_id)
#                 print(f"Found cards: {json.dumps(cards, indent=2)}")

                # print(f"--- Creating a test card in list: {lists[0]['name']} ({first_list_id}) ---")
                # new_card = trello_client.create_card(id_list=first_list_id, name="Test Card from CoPri", desc="This is a test card.")
                # if new_card:
                #     print(f"Created card: {json.dumps(new_card, indent=2)}")

