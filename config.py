"""Configuration management for the email quiz service."""
import os
from dotenv import load_dotenv

load_dotenv()

# Gmail API Configuration
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']

# Email Configuration
TARGET_EMAIL = os.getenv("TARGET_EMAIL", "")
EMAIL_THREAD_ID = os.getenv("EMAIL_THREAD_ID", "")  # Optional: if empty, will create new thread
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Quiz Question")  # Email thread subject/title

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Service Configuration
QUESTIONS_CSV = os.getenv("QUESTIONS_CSV", "review_questions_answer_table.csv")
STATE_FILE = os.getenv("STATE_FILE", "state.json")
SCORES_FILE = os.getenv("SCORES_FILE", "scores.json")  # Track scores per question
PROGRESS_FILE = os.getenv("PROGRESS_FILE", "progress.json")  # Track detailed progress history
REVIEW_SHEET = os.getenv("REVIEW_SHEET", "Galaxie Review Sheet.txt")  # Review sheet for context
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))  # How often to check for responses
QUESTION_INTERVAL_MINUTES = int(os.getenv("QUESTION_INTERVAL_MINUTES", "10"))  # Time between questions

def validate_config():
    """Validate that required configuration is present."""
    errors = []
    
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is required in .env file")
    
    if not TARGET_EMAIL:
        errors.append("TARGET_EMAIL is required in .env file")
    
    if not os.path.exists(GMAIL_CREDENTIALS_FILE):
        errors.append(f"Gmail credentials file not found: {GMAIL_CREDENTIALS_FILE}")
    
    if not os.path.exists(QUESTIONS_CSV):
        errors.append(f"Questions CSV file not found: {QUESTIONS_CSV}")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True
