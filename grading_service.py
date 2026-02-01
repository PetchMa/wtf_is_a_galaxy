"""Gemini API service for grading quiz responses."""
from typing import Dict, Optional
import os
import google.generativeai as genai
import config


class GradingService:
    """Handles grading of quiz responses using Gemini API."""
    
    def __init__(self):
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required in .env file")
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Load review sheet context if available
        self.review_sheet_context = self._load_review_sheet()
        
        # First, list available models to see what we can use
        print("Checking available Gemini models...")
        try:
            all_models = genai.list_models()
            available_models = [
                m.name for m in all_models 
                if 'generateContent' in m.supported_generation_methods
            ]
            print(f"Available models: {available_models}")
            
            # Extract just the model name (remove 'models/' prefix if present)
            model_names_clean = [m.replace('models/', '') for m in available_models]
            
            # Try preferred models in order (cheapest first)
            # Order: lite (cheapest) -> flash -> pro (most expensive)
            preferred_models = [
                'gemini-flash-lite-latest',  # Cheapest option
                'gemini-flash-lite',
                'gemini-2.0-flash-lite',
                'gemini-2.5-flash-lite',
                'gemini-flash-latest',  # Flash (cheaper than pro)
                'gemini-2.0-flash',
                'gemini-2.5-flash',
                'gemini-1.5-flash',
                'gemini-pro-latest',  # Pro (more expensive, fallback)
                'gemini-1.5-pro',
                'gemini-pro'
            ]
            self.model = None
            used_model = None
            
            for preferred in preferred_models:
                # Try to find a matching model in the available list
                for available_full_name in available_models:
                    # Check if this available model matches our preferred model
                    available_clean = available_full_name.replace('models/', '')
                    if preferred in available_clean or available_clean.endswith(preferred):
                        try:
                            self.model = genai.GenerativeModel(available_full_name)
                            used_model = available_full_name
                            print(f"✓ Using Gemini model: {used_model}")
                            break
                        except Exception as e:
                            # Try without 'models/' prefix
                            try:
                                self.model = genai.GenerativeModel(available_clean)
                                used_model = available_clean
                                print(f"✓ Using Gemini model: {used_model}")
                                break
                            except:
                                continue
                if self.model:
                    break
            
            # If no preferred model worked, try the first available model
            if self.model is None and available_models:
                try:
                    self.model = genai.GenerativeModel(available_models[0])
                    used_model = available_models[0]
                    print(f"✓ Using first available Gemini model: {used_model}")
                except Exception as e:
                    pass
            
            if self.model is None:
                raise ValueError(
                    f"Could not initialize any Gemini model.\n"
                    f"Available models: {available_models}\n"
                    "Please check your API key and model availability."
                )
                
        except Exception as e:
            # Fallback: try common model names
            print(f"Warning: Could not list models: {e}")
            print("Trying common model names...")
            model_names = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
            self.model = None
            
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"✓ Using Gemini model: {model_name}")
                    break
                except Exception:
                    continue
            
            if self.model is None:
                raise ValueError(
                    f"Could not initialize Gemini model. Tried: {model_names}\n"
                    "Please check your API key and ensure you have access to Gemini models."
                )
    
    def _load_review_sheet(self) -> Optional[str]:
        """Load review sheet context if available."""
        if os.path.exists(config.REVIEW_SHEET):
            try:
                with open(config.REVIEW_SHEET, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"✓ Loaded review sheet context ({len(content)} characters)")
                    return content
            except Exception as e:
                print(f"Warning: Could not load review sheet: {e}")
                return None
        return None
    
    def grade_response(self, user_response: str, correct_answer: str, question: str) -> Dict:
        """
        Grade a user's response against the correct answer.
        
        Args:
            user_response: The user's answer text
            correct_answer: The known correct answer
            question: The original question (for context)
        
        Returns:
            Dict with 'score' (0-100), 'feedback', and 'missing_points'
        """
        # Build context section if review sheet is available
        context_section = ""
        if self.review_sheet_context:
            # Limit context to avoid token limits (keep last 8000 chars for most recent/relevant content)
            context_text = self.review_sheet_context[-8000:] if len(self.review_sheet_context) > 8000 else self.review_sheet_context
            context_section = f"""

REVIEW SHEET CONTEXT (for reference):
{context_text}
"""
        
        prompt = f"""You are a helpful quiz grader evaluating a student's response for a galaxies/astronomy course. Use the review sheet context provided to give accurate, contextually relevant feedback.

Question: {question}

Correct Answer: {correct_answer}

User's Response: {user_response}
{context_section}
Please provide:
1. A score from 0-100 based on how well the user's response matches the correct answer
2. Specific feedback on what the user got right, referencing concepts from the review sheet when relevant
3. What key points or information the user is missing (if any), and suggest specific sections from the review sheet they should review

Format your response as JSON with the following structure:
{{
    "score": <number 0-100>,
    "feedback": "<overall feedback>",
    "missing_points": ["<point 1>", "<point 2>", ...]
}}

Be fair but thorough. If the user's response captures the essence of the answer even if worded differently, give appropriate credit. Only mark points as missing if they are genuinely absent or incorrect. When providing feedback, reference specific concepts, equations, or sections from the review sheet that are relevant to the question."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Try to extract JSON from the response
            # Sometimes Gemini wraps JSON in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            import json
            result = json.loads(response_text)
            
            # Validate structure
            if 'score' not in result:
                result['score'] = 50  # Default score if parsing fails
            if 'feedback' not in result:
                result['feedback'] = "Unable to generate detailed feedback."
            if 'missing_points' not in result:
                result['missing_points'] = []
            
            return result
            
        except Exception as e:
            # Fallback if API call fails
            return {
                'score': 50,
                'feedback': f"Error grading response: {str(e)}. Please try again.",
                'missing_points': []
            }
    
    def format_feedback_message(self, grade_result: Dict, correct_answer: str = None) -> str:
        """
        Format grading results into a readable feedback message.
        
        Args:
            grade_result: Result from grade_response()
            correct_answer: Optional correct answer to include in feedback
        
        Returns:
            Formatted feedback string
        """
        score = grade_result.get('score', 0)
        feedback = grade_result.get('feedback', '')
        missing_points = grade_result.get('missing_points', [])
        
        message = f"Your Score: {score}/100\n\n"
        message += f"Feedback: {feedback}\n\n"
        
        if missing_points:
            message += "Missing Points:\n"
            for i, point in enumerate(missing_points, 1):
                message += f"{i}. {point}\n"
            message += "\n"
        else:
            message += "Great job! You covered all the key points.\n\n"
        
        # Include the correct answer if provided
        if correct_answer:
            message += "=" * 60 + "\n"
            message += "Correct Answer:\n"
            message += "=" * 60 + "\n"
            message += f"{correct_answer}\n"
        
        return message
