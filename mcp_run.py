import os, base64, email, re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow



"""
    In a Model-Context Protocol (MCP) architecture, external tools are wrapped as microservice
    "connectors" that an AI agent can call. Each tool runs as an independent server exposing 
    capabilities via a standarized interface. 

    This Gmail integration is one such MCP server, acting as intermediary between an autonomous
    AI agent and Gmail. It provides a unified way for the agent to read and search emails,
    without custom-coding Gmail API calls in the agent itself. 
    The microservice uses FastAPI (Python) to expose REST endpoints (tools) for:
    - Email Search - query the Gmail inbox with Gmail's search syntax (eg sender, keywords, labels)
    - Email Read - retrieve an emails content (sibject, sender, date, body) by message ID

"""

import os, base64, email, re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load configuration from .env file or environment
load_dotenv()
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Define Gmail API scope for read-only access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Taken Storage Configuration
TOKEN_STORAGE = os.getenv("TOKEN_STORAGE", "file") # "file" or keyring
TOKEN_PATH = os.getenv("TOKEN_PATH", "token.json")

app = FastAPI(title="Gmail MCP Microservice", version="1.0")

# Global variables for credentials and Gmail API service
creds: Credentials = None
service = None

# Load credentials from storage (file or keyring) if available
def load_credentials():
    global creds
    if TOKEN_STORAGE == "file":
        if os.path.exists(TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            
            
# Initialize on startup: load creds and Gmail service
Before coding, ensure the Gmail API is enabled and OAth credentials are obtained
