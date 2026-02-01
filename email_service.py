"""Gmail API service for sending and receiving quiz emails."""
import base64
import json
import os
from datetime import datetime
from email.mime.text import MIMEText
from typing import Optional, List, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config


class EmailService:
    """Handles Gmail API operations for quiz emails."""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(config.GMAIL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_FILE, config.GMAIL_SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(config.GMAIL_CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {config.GMAIL_CREDENTIALS_FILE}\n"
                        "Please download OAuth2 credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES
                )
                # Use fixed port 8080 - must match redirect URI in Google Cloud Console
                try:
                    creds = flow.run_local_server(port=8080, open_browser=True)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'redirect_uri_mismatch' in error_str or '400' in error_str:
                        # Extract the redirect URI from error if possible
                        import re
                        redirect_match = re.search(r'redirect_uri=([^\s]+)', str(e))
                        redirect_uri = redirect_match.group(1) if redirect_match else 'http://localhost:8080'
                        
                        raise Exception(
                            "\n" + "="*70 + "\n"
                            "REDIRECT URI MISMATCH ERROR\n"
                            "="*70 + "\n"
                            f"The service is trying to use: {redirect_uri}\n"
                            "You need to add this EXACT redirect URI in Google Cloud Console:\n\n"
                            "STEP-BY-STEP FIX:\n"
                            "1. Go to: https://console.cloud.google.com/apis/credentials\n"
                            "2. Select project: wtfgalaxy\n"
                            "3. Click your OAuth 2.0 Client ID\n"
                            "4. Scroll down to 'Authorized redirect URIs'\n"
                            "5. Click '+ ADD URI'\n"
                            f"6. Add EXACTLY: {redirect_uri}\n"
                            "7. Also add (without trailing slash): http://localhost:8080\n"
                            "8. Click 'SAVE' at the bottom\n\n"
                            "IMPORTANT: Make sure your OAuth client type is 'Desktop app',\n"
                            "not 'Web application'. If it's Web app, create a new Desktop app client.\n\n"
                            "After saving, wait 1-2 minutes, then run the service again.\n"
                            "="*70 + "\n"
                        )
                    raise
            
            # Save credentials for next run
            with open(config.GMAIL_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        self.credentials = creds
        self.service = build('gmail', 'v1', credentials=creds)
    
    def send_question(self, question: str, thread_id: Optional[str] = None, subject: Optional[str] = None) -> Dict:
        """
        Send a question email.
        
        Args:
            question: The question text to send
            thread_id: Optional thread ID to reply to. If None and config has thread ID, uses that.
            subject: Optional email subject. If None, uses config.EMAIL_SUBJECT
        
        Returns:
            Dict with 'id' (message ID) and 'threadId' (thread ID)
        """
        if thread_id is None:
            thread_id = config.EMAIL_THREAD_ID
        
        # Handle empty string thread_id (create new thread)
        # Also validate that thread_id looks like a valid Gmail thread ID (long alphanumeric)
        # Gmail thread IDs are typically 16+ character alphanumeric strings
        if not thread_id or (isinstance(thread_id, str) and thread_id.strip() == ''):
            thread_id = None
            print(f"[DEBUG] No thread_id provided, will create new thread")
        elif isinstance(thread_id, str):
            thread_id_clean = thread_id.strip()
            # Gmail thread IDs are typically 16+ character alphanumeric strings
            # But they can be shorter, so let's be more lenient (at least 8 chars)
            if len(thread_id_clean) < 8:
                print(f"[DEBUG] Warning: Thread ID '{thread_id_clean}' seems too short, but will try to use it")
            thread_id = thread_id_clean
            print(f"[DEBUG] Using provided thread_id: {thread_id[:10]}...")
        
        # Use provided subject or default from config
        if subject is None:
            subject = config.EMAIL_SUBJECT
        
        message = MIMEText(question)
        message['to'] = config.TARGET_EMAIL
        message['subject'] = subject if not thread_id else f'Re: {subject}'
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        body = {'raw': raw_message}
        # Only add threadId if it's a valid non-empty string
        if thread_id and isinstance(thread_id, str) and thread_id.strip():
            body['threadId'] = thread_id.strip()
        
        try:
            sent_message = self.service.users().messages().send(
                userId='me', body=body
            ).execute()
            
            return {
                'id': sent_message['id'],
                'threadId': sent_message['threadId']
            }
        except HttpError as error:
            raise Exception(f"Error sending email: {error}")
    
    def send_feedback(self, feedback: str, thread_id: str, subject: Optional[str] = None) -> Dict:
        """
        Send feedback email in the thread.
        
        Args:
            feedback: The feedback text to send
            thread_id: Thread ID to reply to
            subject: Optional email subject. If None, uses config.EMAIL_SUBJECT
        
        Returns:
            Dict with 'id' (message ID) and 'threadId' (thread ID)
        """
        if subject is None:
            subject = config.EMAIL_SUBJECT
        
        message = MIMEText(feedback)
        message['to'] = config.TARGET_EMAIL
        message['subject'] = f'Re: {subject}'
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        body = {
            'raw': raw_message,
            'threadId': thread_id
        }
        
        try:
            sent_message = self.service.users().messages().send(
                userId='me', body=body
            ).execute()
            return {
                'id': sent_message['id'],
                'threadId': sent_message['threadId']
            }
        except HttpError as error:
            raise Exception(f"Error sending feedback: {error}")
    
    def get_thread_messages(self, thread_id: str) -> List[Dict]:
        """
        Get all messages in a thread.
        
        Args:
            thread_id: Thread ID to retrieve messages from
        
        Returns:
            List of message dictionaries with 'id', 'snippet', 'payload', etc.
        """
        try:
            thread = self.service.users().threads().get(
                userId='me', id=thread_id
            ).execute()
            
            return thread.get('messages', [])
        except HttpError as error:
            raise Exception(f"Error retrieving thread: {error}")
    
    def get_latest_message(self, thread_id: str, exclude_message_ids: List[str] = None) -> Optional[Dict]:
        """
        Get the latest message in a thread, excluding specified message IDs.
        
        Args:
            thread_id: Thread ID to check
            exclude_message_ids: List of message IDs to exclude (e.g., the question we sent)
        
        Returns:
            Latest message dict or None if no new messages
        """
        if exclude_message_ids is None:
            exclude_message_ids = []
        
        messages = self.get_thread_messages(thread_id)
        
        # Sort by internal date (newest first)
        messages.sort(key=lambda m: int(m.get('internalDate', 0)), reverse=True)
        
        # Find first message not in exclude list
        for message in messages:
            if message['id'] not in exclude_message_ids:
                return message
        
        return None
    
    def extract_message_text(self, message: Dict) -> str:
        """
        Extract plain text from an email message.
        
        Args:
            message: Message dictionary from Gmail API
        
        Returns:
            Plain text content of the message
        """
        payload = message.get('payload', {})
        
        def extract_from_part(part):
            """Recursively extract text from message parts."""
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif part.get('mimeType') == 'text/html':
                # Fallback to HTML if plain text not available
                data = part.get('body', {}).get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode('utf-8')
                    # Simple HTML tag removal (basic implementation)
                    import re
                    return re.sub('<[^<]+?>', '', html)
            
            # Check for multipart
            parts = part.get('parts', [])
            for subpart in parts:
                text = extract_from_part(subpart)
                if text:
                    return text
            
            return ""
        
        return extract_from_part(payload)
    
    def check_for_response(self, thread_id: str, sent_message_id: str, sent_message_timestamp: int = None, exclude_message_ids: List[str] = None) -> Optional[str]:
        """
        Check if there's a new response in the thread.
        
        Args:
            thread_id: Thread ID to check
            sent_message_id: Message ID of the question we sent (to exclude it)
            sent_message_timestamp: Timestamp (internalDate) of when question was sent
            exclude_message_ids: List of message IDs to exclude (e.g., all service-sent messages)
        
        Returns:
            Response text if found, None otherwise
        """
        if exclude_message_ids is None:
            exclude_message_ids = []
        
        # Always exclude the sent message ID
        if sent_message_id not in exclude_message_ids:
            exclude_message_ids.append(sent_message_id)
        
        # Get the sent message to find its timestamp
        if sent_message_timestamp is None:
            try:
                sent_msg = self.service.users().messages().get(
                    userId='me', id=sent_message_id
                ).execute()
                sent_message_timestamp = int(sent_msg.get('internalDate', 0))
            except:
                sent_message_timestamp = 0
        
        # Get all messages in thread
        messages = self.get_thread_messages(thread_id)
        print(f"[DEBUG] Checking thread with {len(messages)} messages")
        
        # Filter for messages that:
        # 1. Are not any service-sent messages (questions or feedback)
        # 2. Came AFTER the question was sent (with a small buffer to avoid race conditions)
        # 3. Are from the user (target email), not from "me" (service account)
        buffer_ms = 2000  # 2 second buffer to avoid picking up messages sent at the same time
        
        for i, message in enumerate(messages):
            message_id = message.get('id')
            message_timestamp = int(message.get('internalDate', 0))
            
            # Skip any service-sent messages (questions, feedback, etc.)
            if message_id in exclude_message_ids:
                continue
            
            # Only consider messages sent AFTER the question (with buffer)
            time_diff = message_timestamp - sent_message_timestamp
            if time_diff <= buffer_ms:
                print(f"[DEBUG] Message {i+1}: Too early ({time_diff/1000:.1f}s after question, need >{buffer_ms/1000:.1f}s)")
                continue
            
            # Check if message is from the user (target email)
            headers = message.get('payload', {}).get('headers', [])
            from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            
            # Must be from target email, and NOT from "me" (service account)
            from_lower = from_header.lower()
            target_lower = config.TARGET_EMAIL.lower()
            
            print(f"[DEBUG] Message {i+1}: From='{from_header}', Time={time_diff/1000:.1f}s after question")
            print(f"[DEBUG] Message {i+1}: Target email='{config.TARGET_EMAIL}', Match={target_lower in from_lower}")
            
            # IMPORTANT: Only accept messages that are clearly from the user's email address
            # Reject messages that appear to be from the service account
            # Gmail API sends emails as "me" which shows as the user's email, but we can detect
            # service-sent emails by checking if they're in our exclude list or if they're too recent
            
            # Check if it's from the user's email address
            # The email must contain the target email address
            if target_lower not in from_lower:
                print(f"[DEBUG] Message {i+1}: Not from target email (from='{from_header}', target='{config.TARGET_EMAIL}'), skipping")
                continue
            
            if target_lower in from_lower:
                # Additional check: if the message was sent very recently (within 10 seconds of our question),
                # it's likely an automated response, not a user response
                # time_diff is already calculated above
                if time_diff < 10000:  # Less than 10 seconds
                    print(f"⚠️  Message too recent ({time_diff/1000:.1f}s), likely automated, skipping...")
                    continue
                
                # Additional check: Look for common feedback patterns in the message
                # If it contains "Score:" or "Feedback:" it's likely our feedback email
                response_text_preview = self.extract_message_text(message)[:200].lower()
                if any(keyword in response_text_preview for keyword in ['score:', 'your score:', 'feedback:', 'missing points:']):
                    print(f"⚠️  Message appears to be feedback email, skipping...")
                    continue
                
                # Accept messages from the user
                # Note: We can't perfectly distinguish API-sent vs manually-sent emails,
                # but the timestamp check, exclude list, and content checks should catch most cases
                # Extract and check the text - make sure it's not just a quote of the question
                response_text = self.extract_message_text(message)
                
                # Clean up the response text - remove email quote markers
                # Remove common email quote patterns
                import re
                # Remove lines starting with ">" (email quotes)
                response_text = re.sub(r'^>.*$', '', response_text, flags=re.MULTILINE)
                # Remove "On ... wrote:" patterns
                response_text = re.sub(r'On .+ wrote:.*$', '', response_text, flags=re.MULTILINE | re.DOTALL)
                # Remove excessive whitespace
                response_text = re.sub(r'\n\s*\n', '\n', response_text)
                response_text = response_text.strip()
                
                # Basic validation: response must be meaningful
                if len(response_text) < 3:
                    print(f"[DEBUG] Message {i+1}: Response too short ({len(response_text)} chars), skipping")
                    continue
                
                # Don't accept responses that are just the question repeated
                # (sometimes email clients quote the question)
                question_snippet = None
                if sent_message_id:
                    try:
                        sent_msg = self.service.users().messages().get(
                            userId='me', id=sent_message_id
                        ).execute()
                        question_text = self.extract_message_text(sent_msg)
                        if question_text and len(question_text) > 10:
                            # Check if response is mostly the question
                            question_words = set(question_text.lower().split()[:10])  # First 10 words
                            response_words = set(response_text.lower().split())
                            overlap = len(question_words & response_words) / max(len(question_words), 1)
                            if overlap > 0.8:  # More than 80% overlap suggests it's just a quote
                                print(f"[DEBUG] Message {i+1}: Response is likely just a quote of the question (overlap: {overlap:.1%}), ignoring...")
                                continue
                    except:
                        pass
                
                # Return the first valid response found
                print(f"[DEBUG] ✓ Valid response detected from message {i+1}: {response_text[:50]}...")
                return response_text
        
        return None
