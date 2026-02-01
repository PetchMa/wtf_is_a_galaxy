# 🌌 Email Quiz Service - Study via Email with AI Grading

A smart Python service that turns your email inbox into a personalized study companion! Get quiz questions delivered to your email, respond at your own pace, and receive AI-powered feedback with detailed explanations. Perfect for spaced repetition learning and exam preparation.

## ✨ Features

- 📧 **Email-Based Learning**: Questions arrive in your inbox - study anywhere, anytime
- 🤖 **AI-Powered Grading**: Uses Google's Gemini AI to grade your responses and provide detailed feedback
- 📊 **Smart Question Selection**: 
  - Prioritizes unanswered questions first
  - Once all questions are answered, focuses on your weakest areas (lowest scores)
  - Tracks your performance over time
- 📝 **Detailed Feedback**: Get scores, missing points, and the correct answer for every question
- 🧠 **Context-Aware Grading**: The AI has access to your review materials for more accurate feedback
- 📈 **Progress Tracking**: Complete history of all your responses, scores, and feedback saved to `progress.json`
- 🔄 **Thread Continuity**: All questions and feedback stay in one email thread for easy review
- ⏰ **Flexible Timing**: Configurable intervals between questions (default: 10 minutes)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Gmail API**
4. Create **OAuth 2.0 credentials** (Desktop app type)
5. Download the credentials and save as `credentials.json` in the project root

### 3. Get Your Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Copy it (you'll need it for the next step)

### 4. Configure the Service

1. Copy the example environment file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and add your settings:
   ```bash
   # Your email address (where questions will be sent)
   TARGET_EMAIL=your-email@example.com
   
   # Your Gemini API key
   GEMINI_API_KEY=your-gemini-api-key-here
   
   # Optional: Custom email subject
   EMAIL_SUBJECT=My Study Quiz
   ```

### 5. Prepare Your Questions

Edit `review_questions_answer_table.csv` with your questions and answers. The CSV should have columns `questions` and `answers`:

```csv
questions,answers
"What is the capital of France?","Paris is the capital and largest city of France."
"What is 2 + 2?","The answer is 4."
```

### 6. Optional: Add Review Materials

Place your review sheet/document in the project root and reference it in `.env`:
```bash
REVIEW_SHEET=Galaxie Review Sheet.txt
```

The AI will use this as context when grading your responses!

### 7. Run the Service

```bash
python main.py
```

Or with a custom email subject:
```bash
python main.py --subject "Galaxy Midterm Practice"
```

**First Run**: You'll be prompted to authenticate with Gmail in your browser. After authentication, a `token.json` file will be created for future runs.

## 📖 How It Works

1. **Question Delivery**: The service randomly selects a question and emails it to you
2. **You Respond**: Reply to the email with your answer (take your time!)
3. **AI Grading**: Gemini AI grades your response against the correct answer
4. **Feedback**: You receive detailed feedback including:
   - Your score (0-100)
   - What you got right/wrong
   - Missing points
   - The correct answer
5. **Next Question**: After 10 minutes (configurable), you get a new question
6. **Smart Selection**: The service learns from your performance and prioritizes questions you struggle with

## 🎯 Advanced Features

### Performance Tracking

- **Scores File** (`scores.json`): Tracks average scores per question for weighted selection
- **Progress File** (`progress.json`): Complete history with timestamps, your responses, feedback, and scores
- **State File** (`state.json`): Current session state (automatically managed)

### Question Selection Strategy

- **Phase 1**: All questions get asked at least once (prioritizes unanswered)
- **Phase 2**: Once all questions are answered, focuses on lowest-scoring questions
- **Recent Questions**: Avoids asking the same question too frequently (last 10 questions excluded)

### Customization Options

Edit `.env` to customize:
- `QUESTION_INTERVAL_MINUTES`: Time between questions (default: 10)
- `POLL_INTERVAL_SECONDS`: How often to check for responses (default: 30)
- `QUESTIONS_CSV`: Path to your questions file
- `REVIEW_SHEET`: Path to your review materials for AI context

### Command Line Options

```bash
# Reset state and start fresh
python main.py --reset

# Custom email subject
python main.py --subject "Final Exam Prep"

# Both
python main.py --subject "Practice Quiz" --reset
```

## 🛠️ Troubleshooting

### Gmail Authentication Issues
- **Error: redirect_uri_mismatch**: Make sure you created "Desktop app" credentials (not Web app)
- **Error: access_denied**: Add your email as a test user in Google Cloud Console OAuth consent screen
- **Re-authenticate**: Delete `token.json` and run again

### API Issues
- **Gemini API errors**: Check that your API key is correct in `.env`
- **Model not found**: The service automatically selects the best available Gemini model

### Response Detection
- **Not detecting responses**: Make sure you're replying in the same email thread
- **Too strict filtering**: Check debug output - the service filters out automated messages

### State Issues
- **Reset everything**: Use `python main.py --reset` to clear state and scores
- **Keep progress history**: Progress history in `progress.json` is preserved on reset

## 📁 Project Structure

```
wtf_is_a_galaxy/
├── main.py                          # Main service loop
├── email_service.py                 # Gmail API integration
├── grading_service.py               # Gemini AI grading
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── review_questions_answer_table.csv # Your questions (edit this!)
├── Galaxie Review Sheet.txt         # Optional: Review materials
├── .env                             # Your configuration (not in git)
├── env.example                      # Configuration template
├── credentials.json                 # Gmail OAuth (not in git)
├── token.json                       # Gmail auth token (not in git)
├── state.json                       # Runtime state (not in git)
├── scores.json                      # Performance tracking (not in git)
└── progress.json                    # Complete history (not in git)
```

## 🔒 Security

All sensitive files are automatically excluded from git:
- `.env` - Your API keys and configuration
- `token.json` - Gmail authentication token
- `credentials.json` - OAuth credentials
- `state.json`, `scores.json`, `progress.json` - Your personal data

**Never commit these files!** The `.gitignore` file protects them automatically.

## 💡 Tips

- **Study Regularly**: The spaced repetition works best with consistent practice
- **Review Progress**: Check `progress.json` to see your improvement over time
- **Customize Questions**: Edit the CSV file to add/remove questions anytime
- **Use Review Materials**: Add your study guides - the AI uses them for better feedback
- **Thread Management**: All questions stay in one email thread for easy review

## 🎓 Perfect For

- Exam preparation
- Spaced repetition learning
- Self-assessment
- Reviewing large question banks
- Learning on-the-go via email

## 📝 License

This project is open source. Feel free to use, modify, and share!

---

**Happy Studying! 🌟** Turn your inbox into a learning machine!
