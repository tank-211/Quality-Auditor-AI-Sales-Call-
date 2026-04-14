📞 AI Call QA Analyzer (Local LLM Powered)

An AI-powered system that analyzes call transcripts, evaluates agent performance, and automates quality auditing using a local LLM via Ollama — ensuring zero API cost and full data privacy.

🚀 Features
Sentiment Analysis (Positive / Neutral / Negative)
AI-based Call Quality Evaluation
Structured Call Summary Generation
Agent Performance Scoring (QA Parameters)
Automated Excel Report Generation (Master + Agent-wise)
Email Notifications to TL, Agent, and Auditor
Fully Local Processing (No external APIs)
⚙️ How It Works
Transcript (.txt)
        ↓
Local LLM (Ollama)
        ↓
Call Analysis (Scores + Summary)
        ↓
Excel Reports Generated
        ↓
Email Notifications Sent
🛠️ Tech Stack
Python
Pandas
Watchdog
SMTP (Email Automation)
Ollama (Local LLM)
📂 Project Structure
/transcripts        # Input call files (ignored in git)
/reports            # Generated reports (ignored in git)
/config             # Agent email mapping
app.py              # Main application
requirements.txt    # Dependencies
⚡ Setup Instructions
1. Clone the repo
git clone https://github.com/tank-211/Quality-Auditor-AI-Sales-Call-.git
cd Quality-Auditor-AI-Sales-Call-
2. Install dependencies
pip install -r requirements.txt
3. Install & Run Ollama

Install Ollama and run:

ollama run phi
4. Configure Email

Update credentials in app.py or use environment variables:

SMTP_EMAIL=your_email
SMTP_PASSWORD=your_app_password
5. Run the application
python app.py
📌 Usage
Add transcript file:
transcripts/agent_001/14-04-2026_001.txt
System will automatically:
Analyze call
Generate scores
Save reports
Send emails
⚠️ Important Notes
Generated files (transcripts, reports, .xlsx) are excluded using .gitignore
Do not upload sensitive call data
Ensure Ollama is running locally
🔮 Future Improvements
Web dashboard
Real-time call processing
Database integration
Multi-language support
📄 License

MIT License
