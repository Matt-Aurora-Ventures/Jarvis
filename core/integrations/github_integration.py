# This is /home/ubuntu/copri_app/src/integrations/github_integration.py
import requests
import json
import base64 # For encoding file content for GitHub API

GITHUB_API_BASE_URL = "https://api.github.com"

class GitHubIntegration:
    def __init__(self, token=None):
        """Initializes the GitHub client.
        token: Personal Access Token for authentication.
        """
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28" # Recommended by GitHub
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}" # Using Bearer token type

    def get_authenticated_user_info(self):
        """Fetches information about the authenticated user to verify token and permissions."""
        if not self.token:
            print("[GitHubIntegration] Token not provided. Cannot fetch authenticated user info.")
            return None
        url = f"{GITHUB_API_BASE_URL}/user"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            print("[GitHubIntegration] Successfully fetched authenticated user info.")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching authenticated GitHub user info: {e}")
            # It's good practice to check if response exists before accessing its attributes
            if 'response' in locals() and response is not None:
                print(f"Response status: {response.status_code}, Response content: {response.text}")
            return None

    def create_repository(self, repo_name, description="", private=False, auto_init=False):
        """Creates a new repository for the authenticated user."""
        if not self.token:
            print("[GitHubIntegration] Token not provided. Cannot create repository.")
            return None
        
        url = f"{GITHUB_API_BASE_URL}/user/repos"
        payload = {
            "name": repo_name,
            "description": description,
            "private": private,
            "auto_init": auto_init 
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            print(f"[GitHubIntegration] Successfully created repository: {response.json().get('html_url')}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating GitHub repository {repo_name}: {e}")
            if hasattr(response, 'status_code'):
                 print(f"Response status: {response.status_code}, Response content: {response.text}")
            return None

    def get_file_sha(self, owner, repo, file_path, branch="main"):
        """Gets the SHA of a file if it exists. Returns None if not found."""
        if not self.token:
            print("[GitHubIntegration] Token not provided. Cannot get file SHA.")
            return None
        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{file_path}?ref={branch}"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return None # File not found
            response.raise_for_status()
            return response.json().get("sha")
        except requests.exceptions.RequestException as e:
            print(f"Error getting SHA for file {file_path} in {owner}/{repo}: {e}")
            return None

    def upload_or_update_file(self, owner, repo, file_path, file_content_str, commit_message, branch="main"):
        """Uploads a new file or updates an existing file in a repository."""
        if not self.token:
            print("[GitHubIntegration] Token not provided. Cannot upload/update file.")
            return None

        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{file_path}"
        
        encoded_content = base64.b64encode(file_content_str.encode("utf-8")).decode("utf-8")
        
        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch
        }
        
        sha = self.get_file_sha(owner, repo, file_path, branch)
        if sha:
            payload["sha"] = sha
            print(f"[GitHubIntegration] Updating existing file: {file_path} in {owner}/{repo}")
        else:
            print(f"[GitHubIntegration] Creating new file: {file_path} in {owner}/{repo}")

        try:
            response = requests.put(url, headers=self.headers, json=payload)
            response.raise_for_status()
            print(f"[GitHubIntegration] Successfully uploaded/updated file: {file_path}. Commit: {response.json()['commit']['sha']}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error uploading/updating file {file_path} to {owner}/{repo}: {e}")
            if hasattr(response, 'status_code'):
                print(f"Response status: {response.status_code}, Response content: {response.text}")
            return None

    def get_user_repos(self, username=None):
        """Fetches repositories for the authenticated user or a specified user."""
        if username:
            url = f"{GITHUB_API_BASE_URL}/users/{username}/repos"
        else:
            if not self.token: 
                print("[GitHubIntegration] Token required to fetch authenticated user's repos.")
                return []
            url = f"{GITHUB_API_BASE_URL}/user/repos"
        
        params = {"type": "owner", "sort": "updated", "per_page": 10}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            print(f"[GitHubIntegration] Fetched repositories for {	'authenticated user' if not username else username}.")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching GitHub repositories: {e}")
            return []

    def get_repo_issues(self, owner, repo, state="open"):
        """Fetches issues for a specific repository."""
        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": 10}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            print(f"[GitHubIntegration] Fetched issues for {owner}/{repo}.")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issues for {owner}/{repo}: {e}")
            return []

