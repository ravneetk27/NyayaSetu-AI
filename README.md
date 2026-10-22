---
title: NyayaSetu AI
emoji: ⚖️
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# ⚖️ NyayaSetu AI (न्यायसेतु)
### AI-Powered Legal Advisory & Complaint Drafting Agent for PoSH & POCSO

NyayaSetu AI is an intelligent legal assistant designed to help victims and legal advisors navigate the **Protection of Women from Sexual Harassment (PoSH) Act, 2013** and the **Protection of Children from Sexual Offences (POCSO) Act, 2012**.

---

## 🌟 Key Features

- **Empathetic & Confidential Interaction**: Structured interview to gather facts safely.
- **RAG-Powered Legal Retrieval**: Context-aware retrieval of PoSH/POCSO statutory provisions, timelines, and landmark precedents using `SentenceTransformers`.
- **Automated Complaint Drafting**: Generates formal complaints in PDF and Word format following Indian legal drafting standards.
- **Strict Privacy**: Data is processed in-memory or locally; credentials and documents are not persisted insecurely.

---

## 🚀 Environment Variables

When deploying to Hugging Face Spaces or your cloud provider, set the following secrets/environment variables:

| Variable | Description | Required |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Your Groq API key for high-speed LLM generation | **Yes** |
| `LLM_MODEL` | LLM model identifier (default: `qwen/qwen3.8-27b`) | Optional |
| `PORT` | Listening port (defaults to `7860` on Spaces, `8000` locally) | Optional |

---

## 🛠️ Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ravneetk27/NyayaSetu-AI.git
   cd NyayaSetu-AI
   ```

2. **Set up virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment:**
   Create a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

4. **Run the server:**
   ```bash
   python backend/run.py
   ```
   Open your browser at `http://localhost:8000`.
