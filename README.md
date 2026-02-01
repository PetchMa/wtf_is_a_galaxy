# Email Quiz Service

A local Python service that sends quiz questions via Gmail, waits for your email responses, grades them using Google's Gemini API, and sends new questions every 10 minutes.

## Features

- Randomly selects questions from a CSV file
- Sends questions via Gmail in a specific email thread
- Waits for your email response
- Grades responses using Gemini AI
- Provides detailed feedback on what you're missing
- Schedules new questions 10 minutes after you respond

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download the credentials and save as `credentials.json` in the project root

### 3. Gemini API Setup

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Copy the API key

### 4. Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in:
   - `GEMINI_API_KEY`: Your Gemini API key
   - `TARGET_EMAIL`: Your email address (where questions will be sent)
   - `EMAIL_THREAD_ID`: (Optional) Leave empty to create a new thread, or provide an existing thread ID

### 5. Prepare Questions

Edit `questions.csv` with your questions and answers. Format:
```csv
question,answer
What is the capital of France?,Paris is the capital and largest city of France.
What is 2 + 2?,The answer is 4.
```

## Usage

Run the service:
```bash
python main.py
```

On first run, you'll be prompted to authenticate with Gmail in your browser. After authentication, a `token.json` file will be created for future runs.

The service will:
1. Send a random question to your email
2. Wait for your response in the email thread
3. Grade your response using Gemini
4. Send feedback back via email
5. Wait 10 minutes, then send a new question

Press `Ctrl+C` to stop the service. State is automatically saved and will be restored on restart.

## Configuration Options

Edit `.env` to customize:

- `QUESTION_INTERVAL_MINUTES`: Time between questions (default: 10)
- `POLL_INTERVAL_SECONDS`: How often to check for responses (default: 30)
- `QUESTIONS_CSV`: Path to questions file (default: questions.csv)
- `STATE_FILE`: Path to state file (default: state.json)

## How It Works

1. **Question Selection**: Randomly picks from CSV, avoiding recently asked questions
2. **Email Threading**: Uses Gmail's thread ID to maintain conversation context
3. **Response Detection**: Polls Gmail API for new messages in the thread
4. **AI Grading**: Sends your response + correct answer to Gemini for evaluation
5. **Feedback**: Replies to thread with score and missing points
6. **Scheduling**: Waits 10 minutes after feedback before sending next question

## Troubleshooting

- **Gmail Authentication**: Delete `token.json` and run again to re-authenticate
- **API Errors**: Check that your API keys are correct in `.env`
- **No Responses Detected**: Ensure you're replying in the same email thread
- **State Issues**: Delete `state.json` to reset (you'll lose current question state)

## Files

- `main.py`: Main service loop
- `email_service.py`: Gmail API integration
- `grading_service.py`: Gemini API integration
- `config.py`: Configuration management
- `questions.csv`: Questions and answers
- `state.json`: Runtime state (auto-generated)
