"""Main service loop for the email quiz system."""
import argparse
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import pandas as pd
import config
from email_service import EmailService
from grading_service import GradingService


class QuizService:
    """Main service that orchestrates the quiz system."""
    
    def __init__(self, email_subject: Optional[str] = None, reset_state: bool = False, reset_waiting: bool = True):
        self.email_service = EmailService()
        self.grading_service = GradingService()
        self.questions_df = None
        self.email_subject = email_subject or config.EMAIL_SUBJECT
        
        # Reset state completely if requested
        if reset_state:
            if os.path.exists(config.STATE_FILE):
                os.remove(config.STATE_FILE)
            if os.path.exists(config.SCORES_FILE):
                os.remove(config.SCORES_FILE)
            # Note: We don't clear progress file on reset - that's your history!
            print("✓ Cleared state and scores files (progress history preserved)")
        
        self.state = self._load_state(reset_waiting=reset_waiting)
        self.scores = self._load_scores()
        self.progress = self._load_progress()
        self._load_questions()
    
    def _load_questions(self):
        """Load questions from CSV file."""
        if not os.path.exists(config.QUESTIONS_CSV):
            raise FileNotFoundError(f"Questions file not found: {config.QUESTIONS_CSV}")
        
        self.questions_df = pd.read_csv(config.QUESTIONS_CSV)
        
        # Handle both singular and plural column names
        # Normalize column names: 'questions' -> 'question', 'answers' -> 'answer'
        column_mapping = {}
        if 'questions' in self.questions_df.columns:
            column_mapping['questions'] = 'question'
        if 'answers' in self.questions_df.columns:
            column_mapping['answers'] = 'answer'
        
        if column_mapping:
            self.questions_df = self.questions_df.rename(columns=column_mapping)
        
        # Validate CSV structure
        required_columns = ['question', 'answer']
        missing = [col for col in required_columns if col not in self.questions_df.columns]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}. Found columns: {list(self.questions_df.columns)}")
        
        # Check if CSV file has changed (different number of questions)
        # If so, clear recent_questions and current_question_idx to avoid index mismatches
        num_questions = len(self.questions_df)
        if self.state.get('recent_questions'):
            # Check if any recent question index is out of bounds
            max_idx = max(self.state.get('recent_questions', [0]))
            if max_idx >= num_questions:
                print(f"⚠️  Warning: State has question indices that don't match new CSV ({num_questions} questions). Clearing recent questions.")
                self.state['recent_questions'] = []
                self.state['current_question_idx'] = None
                self.state['current_question'] = None
                self.state['current_answer'] = None
        
        print(f"Loaded {len(self.questions_df)} questions from {config.QUESTIONS_CSV}")
    
    def _load_state(self, reset_waiting: bool = True) -> Dict:
        """Load state from JSON file.
        
        Args:
            reset_waiting: If True, reset waiting state on startup (default: True)
        """
        if os.path.exists(config.STATE_FILE):
            try:
                with open(config.STATE_FILE, 'r') as f:
                    state = json.load(f)
                
                # Reset waiting state on startup to allow new questions
                if reset_waiting:
                    state['waiting_for_response'] = False
                    state['current_question'] = None
                    state['current_answer'] = None
                    state['sent_message_id'] = None
                    state['sent_message_timestamp'] = None
                    # Keep thread_id and last_question_time for continuity
                    # Ensure thread_id is preserved (don't clear it)
                    if 'thread_id' in state and state['thread_id']:
                        print(f"✓ Reset waiting state on startup (keeping thread ID: {state['thread_id'][:10]}...)")
                    else:
                        print("✓ Reset waiting state on startup (no existing thread)")
                
                return state
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {config.STATE_FILE}, starting fresh")
        
        # Ensure thread_id is None if empty string
        thread_id = config.EMAIL_THREAD_ID
        if not thread_id or (isinstance(thread_id, str) and thread_id.strip() == ''):
            thread_id = None
        
        return {
            'current_question': None,
            'current_answer': None,
            'thread_id': thread_id,
            'sent_message_id': None,
            'last_question_time': None,
            'waiting_for_response': False,
            'recent_questions': []  # Track recently asked questions
        }
    
    def _load_scores(self) -> Dict:
        """Load question scores from JSON file."""
        if os.path.exists(config.SCORES_FILE):
            try:
                with open(config.SCORES_FILE, 'r') as f:
                    scores = json.load(f)
                    # Convert string keys to ints
                    return {int(k): v for k, v in scores.items()}
            except (json.JSONDecodeError, ValueError):
                print(f"Warning: Could not parse {config.SCORES_FILE}, starting fresh")
        
        return {}  # {question_index: [list of scores]}
    
    def _save_scores(self):
        """Save question scores to JSON file."""
        with open(config.SCORES_FILE, 'w') as f:
            json.dump(self.scores, f, indent=2)
    
    def _load_progress(self) -> list:
        """Load progress history from JSON file."""
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {config.PROGRESS_FILE}, starting fresh")
        
        return []
    
    def _save_progress(self):
        """Save progress history to JSON file."""
        with open(config.PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _record_progress(self, question: str, user_response: str, feedback: str, score: int, question_idx: Optional[int] = None):
        """Record a progress entry with timestamp."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'question_idx': question_idx,
            'question': question,
            'user_response': user_response,
            'feedback': feedback,
            'score': score
        }
        self.progress.append(entry)
        self._save_progress()
        print(f"✓ Progress recorded to {config.PROGRESS_FILE}")
    
    def _record_score(self, question_idx: int, score: int):
        """Record a score for a question."""
        if question_idx not in self.scores:
            self.scores[question_idx] = []
        self.scores[question_idx].append(score)
        self._save_scores()
    
    def _get_average_score(self, question_idx: int) -> float:
        """Get the average score for a question. Returns 100 if never answered."""
        if question_idx not in self.scores or len(self.scores[question_idx]) == 0:
            return 100.0  # Default to 100 (perfect) if never answered
        return sum(self.scores[question_idx]) / len(self.scores[question_idx])
    
    def _save_state(self):
        """Save current state to JSON file."""
        # Convert numpy/pandas types to native Python types for JSON serialization
        def convert_to_native(obj):
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif hasattr(obj, 'item'):  # numpy/pandas scalar types
                return obj.item()
            elif isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            else:
                return str(obj)  # Fallback: convert to string
        
        state_to_save = convert_to_native(self.state)
        with open(config.STATE_FILE, 'w') as f:
            json.dump(state_to_save, f, indent=2)
    
    def _select_random_question(self) -> Dict:
        """
        Select a question with smart prioritization:
        1. First, prioritize questions that have never been answered
        2. Once all questions have been answered at least once, prioritize by lowest average score
        """
        # Filter out recently asked questions (last 10)
        # Convert to native ints for comparison
        recent = set(int(q) for q in self.state.get('recent_questions', []))
        available = self.questions_df[~self.questions_df.index.isin(recent)]
        
        # If all questions have been asked recently, reset
        if len(available) == 0:
            available = self.questions_df
            self.state['recent_questions'] = []
        
        # Separate questions into: unanswered vs answered
        unanswered_indices = []
        answered_indices = []
        
        for idx, row in available.iterrows():
            question_idx = int(idx)
            # Check if question has been answered (has scores recorded)
            if question_idx not in self.scores or len(self.scores[question_idx]) == 0:
                unanswered_indices.append(question_idx)
            else:
                answered_indices.append(question_idx)
        
        # Strategy 1: If there are unanswered questions, prioritize them
        if len(unanswered_indices) > 0:
            # Randomly select from unanswered questions (equal probability)
            selected_idx = random.choice(unanswered_indices)
            selected = self.questions_df.loc[selected_idx]
            question_idx = int(selected_idx)
            
            # Update recent questions (keep last 10)
            recent_questions = [int(q) if hasattr(q, 'item') else int(q) for q in self.state.get('recent_questions', [])]
            self.state['recent_questions'] = (recent_questions + [question_idx])[-10:]
            
            print(f"Selected question (unanswered, {len(unanswered_indices)} remaining)")
            return {
                'question': selected['question'],
                'answer': selected['answer'],
                'index': question_idx
            }
        
        # Strategy 2: All questions have been answered at least once
        # Now prioritize by lowest average score
        total_questions = len(self.questions_df)
        answered_count = len(self.scores)
        print(f"Progress: {answered_count}/{total_questions} questions answered at least once")
        
        # Calculate weights based on scores (lower scores = higher weight)
        # Weight = (101 - average_score) to invert: score 0 = weight 101, score 100 = weight 1
        weights = []
        available_indices = []
        
        for idx, row in available.iterrows():
            question_idx = int(idx)
            avg_score = self._get_average_score(question_idx)
            # Weight inversely proportional to score (lower score = higher weight)
            # Use a stronger weighting: (101 - score)^2 to make low scores much more likely
            weight = (101.0 - avg_score) ** 2
            # Minimum weight of 1 to ensure all questions have some chance
            weight = max(1.0, weight)
            weights.append(weight)
            available_indices.append(question_idx)
        
        # Normalize weights to probabilities
        total_weight = sum(weights)
        if total_weight > 0:
            probabilities = [w / total_weight for w in weights]
        else:
            # Equal probability if all weights are 0 (shouldn't happen)
            probabilities = [1.0 / len(weights)] * len(weights)
        
        # Select question based on weighted probabilities
        selected_idx = random.choices(available_indices, weights=probabilities, k=1)[0]
        selected = self.questions_df.loc[selected_idx]
        question_idx = int(selected_idx)
        
        # Update recent questions (keep last 10)
        # Convert any existing int64 values to native ints
        recent_questions = [int(q) if hasattr(q, 'item') else int(q) for q in self.state.get('recent_questions', [])]
        self.state['recent_questions'] = (recent_questions + [question_idx])[-10:]
        
        # Show selection info
        avg_score = self._get_average_score(question_idx)
        print(f"Selected question (avg score: {avg_score:.1f}/100, prioritizing lowest scores)")
        
        return {
            'question': selected['question'],
            'answer': selected['answer'],
            'index': question_idx
        }
    
    def _should_send_new_question(self) -> bool:
        """Check if it's time to send a new question."""
        # If no question was ever sent, send one immediately
        if not self.state.get('last_question_time'):
            print(f"[DEBUG] Should send: No previous question time")
            return True
        
        # If last question failed (no sent_message_id), send immediately
        if not self.state.get('sent_message_id'):
            print(f"[DEBUG] Should send: No sent_message_id (previous send may have failed)")
            return True
        
        # Otherwise, check if enough time has passed
        last_time_str = self.state['last_question_time']
        last_time = datetime.fromisoformat(last_time_str)
        interval = timedelta(minutes=config.QUESTION_INTERVAL_MINUTES)
        time_since = datetime.now() - last_time
        
        should_send = time_since >= interval
        if not should_send:
            remaining = interval - time_since
            print(f"[DEBUG] Not time yet. {remaining.total_seconds()/60:.1f} minutes remaining until next question.")
        
        return should_send
    
    def _send_question(self):
        """Send a new question via email."""
        question_data = self._select_random_question()
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sending question...")
        print(f"Question: {question_data['question'][:100]}...")
        print(f"Subject: {self.email_subject}")
        
        try:
            # Get thread_id from state, preserving it for thread continuity
            thread_id = self.state.get('thread_id')
            if not thread_id or (isinstance(thread_id, str) and thread_id.strip() == ''):
                thread_id = None
                print(f"[DEBUG] No existing thread_id, will create new thread")
            else:
                print(f"[DEBUG] Using existing thread_id: {thread_id[:10]}...")
            
            result = self.email_service.send_question(
                question_data['question'],
                thread_id=thread_id,
                subject=self.email_subject
            )
            
            # Get the actual message to get its timestamp
            try:
                sent_msg = self.email_service.service.users().messages().get(
                    userId='me', id=result['id']
                ).execute()
                sent_message_timestamp = int(sent_msg.get('internalDate', 0))
            except Exception as e:
                # Fallback to current time if we can't get message
                print(f"Warning: Could not get message timestamp: {e}")
                sent_message_timestamp = int(datetime.now().timestamp() * 1000)
            
            # Update state
            self.state['current_question'] = question_data['question']
            self.state['current_answer'] = question_data['answer']
            self.state['current_question_idx'] = question_data['index']
            self.state['sent_message_id'] = result['id']
            self.state['sent_message_timestamp'] = sent_message_timestamp
            self.state['thread_id'] = result['threadId']
            self.state['last_question_time'] = datetime.now().isoformat()
            self.state['waiting_for_response'] = True
            
            # Track all sent message IDs to exclude from response detection
            if 'sent_message_ids' not in self.state:
                self.state['sent_message_ids'] = []
            self.state['sent_message_ids'].append(result['id'])
            # Keep only last 10 to avoid growing too large
            self.state['sent_message_ids'] = self.state['sent_message_ids'][-10:]
            
            self._save_state()
            
            print(f"✓ Question sent successfully!")
            print(f"  Message ID: {result['id']}")
            print(f"  Thread ID: {result['threadId']}")
            print(f"  Waiting for response...")
            
        except Exception as e:
            print(f"✗ Error sending question: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise - allow service to continue and try again later
            self.state['waiting_for_response'] = False
            self.state['sent_message_id'] = None
            self._save_state()
    
    def _check_for_response(self) -> Optional[str]:
        """Check if there's a response to the current question."""
        if not self.state.get('waiting_for_response'):
            return None
        
        thread_id = self.state.get('thread_id')
        sent_message_id = self.state.get('sent_message_id')
        
        if not thread_id or not sent_message_id:
            return None
        
        # Get timestamp of when question was sent (saved when question was sent)
        sent_timestamp = self.state.get('sent_message_timestamp')
        
        # Get all sent message IDs to exclude (questions and feedback)
        sent_message_ids = self.state.get('sent_message_ids', [])
        if sent_message_id not in sent_message_ids:
            sent_message_ids.append(sent_message_id)
        
        try:
            response = self.email_service.check_for_response(
                thread_id, 
                sent_message_id,
                sent_message_timestamp=sent_timestamp,
                exclude_message_ids=sent_message_ids
            )
            if response:
                print(f"[DEBUG] Response detected: {response[:50]}...")
            return response
        except Exception as e:
            print(f"✗ Error checking for response: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _grade_and_send_feedback(self, user_response: str):
        """Grade the user's response and send feedback."""
        question = self.state.get('current_question')
        correct_answer = self.state.get('current_answer')
        question_idx = None
        
        # Get question index from state if available
        if 'current_question_idx' in self.state:
            question_idx = self.state['current_question_idx']
        
        if not question or not correct_answer:
            print("Error: Missing question or answer in state")
            return
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Grading response...")
        print(f"User response: {user_response[:100]}...")
        
        try:
            grade_result = self.grading_service.grade_response(
                user_response, correct_answer, question
            )
            
            score = grade_result.get('score', 0)
            
            # Record the score if we have the question index
            if question_idx is not None:
                self._record_score(question_idx, score)
                avg_score = self._get_average_score(question_idx)
                print(f"Score recorded: {score}/100 (average: {avg_score:.1f}/100)")
            
            feedback_message = self.grading_service.format_feedback_message(
                grade_result,
                correct_answer=correct_answer
            )
            
            # Send feedback email
            feedback_result = self.email_service.send_feedback(
                feedback_message,
                self.state['thread_id'],
                subject=self.email_subject
            )
            
            # Track feedback message ID so we don't pick it up as a response
            if 'sent_message_ids' not in self.state:
                self.state['sent_message_ids'] = []
            if feedback_result and 'id' in feedback_result:
                self.state['sent_message_ids'].append(feedback_result['id'])
                # Keep only last 10 to avoid growing too large
                self.state['sent_message_ids'] = self.state['sent_message_ids'][-10:]
                self._save_state()
            
            # Record progress history
            self._record_progress(
                question=question,
                user_response=user_response,
                feedback=feedback_message,
                score=score,
                question_idx=question_idx
            )
            
            print(f"Feedback sent! Score: {score}/100")
            
            # Update state
            self.state['waiting_for_response'] = False
            self.state['current_question'] = None
            self.state['current_answer'] = None
            self.state['current_question_idx'] = None
            self.state['sent_message_id'] = None
            self.state['sent_message_timestamp'] = None
            self._save_state()
            
        except Exception as e:
            print(f"Error grading response: {e}")
            # Still mark as not waiting so we can continue
            self.state['waiting_for_response'] = False
            self._save_state()
    
    def run(self):
        """Main service loop."""
        print("=" * 60)
        print("Email Quiz Service Starting...")
        print("=" * 60)
        
        # Validate configuration
        try:
            config.validate_config()
        except ValueError as e:
            print(f"Configuration error: {e}")
            return
        
        print(f"Target email: {config.TARGET_EMAIL}")
        print(f"Question interval: {config.QUESTION_INTERVAL_MINUTES} minutes")
        print(f"Poll interval: {config.POLL_INTERVAL_SECONDS} seconds")
        print("\nPress Ctrl+C to stop the service\n")
        
        try:
            while True:
                # Check if we should send a new question
                if not self.state.get('waiting_for_response') and self._should_send_new_question():
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ready to send new question...")
                    self._send_question()
                
                # Check for responses if we're waiting
                if self.state.get('waiting_for_response'):
                    # Check if we've been waiting too long (timeout after 2x the question interval)
                    last_time_str = self.state.get('last_question_time')
                    if last_time_str:
                        last_time = datetime.fromisoformat(last_time_str)
                        timeout_interval = timedelta(minutes=config.QUESTION_INTERVAL_MINUTES * 2)
                        if datetime.now() - last_time >= timeout_interval:
                            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Timeout: No response received. Resetting state to send new question.")
                            self.state['waiting_for_response'] = False
                            self.state['sent_message_id'] = None
                            self._save_state()
                            continue
                    
                    # Only check for response, don't spam waiting messages
                    response = self._check_for_response()
                    if response:
                        current_question = self.state.get('current_question', 'Unknown')
                        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Response received!")
                        print(f"Question: {current_question[:50]}...")
                        print(f"Response: {response[:100]}...")
                        self._grade_and_send_feedback(response)
                
                # Sleep before next iteration
                time.sleep(config.POLL_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            print("\n\nService stopped by user.")
            self._save_state()
            print("State saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Email Quiz Service - Study via email with AI grading')
    parser.add_argument(
        '--subject',
        type=str,
        default=None,
        help='Email thread subject/title (default: "Quiz Question" or from EMAIL_SUBJECT in .env)'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset/clear state on startup (removes state.json and scores.json)'
    )
    
    args = parser.parse_args()
    
    # Reset state if requested
    service = QuizService(
        email_subject=args.subject,
        reset_state=args.reset,
        reset_waiting=True  # Always reset waiting state on startup
    )
    service.run()
