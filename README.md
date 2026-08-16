<h1 align="center">🔎 Multi-Agent Research System</h1>

<p align="center">
  <strong>AI-Powered Autonomous Research & Report Generation System</strong>
</p>

<p align="center">
  Search • Read • Write • Critique
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/LangChain-Agentic%20AI-green?style=for-the-badge">
  <img src="https://img.shields.io/badge/Groq-LLM-orange?style=for-the-badge">
  <img src="https://img.shields.io/badge/Tavily-Web%20Search-purple?style=for-the-badge">
  <img src="https://img.shields.io/badge/Streamlit-Application-red?style=for-the-badge&logo=streamlit">
</p>

<hr>

<h2>🚀 Overview</h2>

<p>
The <strong>Multi-Agent Research System</strong> is an AI-powered research
application designed to automate the complete research workflow.
Instead of relying on a single LLM call, the system divides the task
among multiple specialized AI agents.
</p>

<p>
The system can search the web for recent information, identify relevant
resources, extract deeper content from selected websites, generate a
structured research report, and finally evaluate the generated report
using a dedicated critic agent.
</p>

<p>
The complete pipeline follows:
</p>

<p align="center">
  <strong>🔍 Search → 📖 Read → ✍️ Write → 🧐 Critique</strong>
</p>

<hr>

<h2>🎯 Project Objective</h2>

<p>
Traditional LLM applications often depend on a single model response.
This project demonstrates how an <strong>Agentic AI architecture</strong>
can divide a complex task into smaller responsibilities and allow
different agents to perform specialized operations.
</p>

<p>The main objectives are:</p>

<ul>
  <li>Automate web-based research</li>
  <li>Retrieve recent and relevant information</li>
  <li>Read and extract information from web pages</li>
  <li>Generate structured research reports</li>
  <li>Critically evaluate generated reports</li>
  <li>Provide an interactive Streamlit interface</li>
  <li>Allow users to download the final report</li>
</ul>

<hr>

<h2>🧠 System Architecture</h2>

<pre>
                    ┌──────────────────────┐
                    │        USER          │
                    │   Research Topic     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    SEARCH AGENT      │
                    │                      │
                    │      Tavily API      │
                    └──────────┬───────────┘
                               │
                         Search Results
                               │
                               ▼
                    ┌──────────────────────┐
                    │     READER AGENT     │
                    │                      │
                    │ Requests + Beautiful │
                    │       Soup           │
                    └──────────┬───────────┘
                               │
                         Scraped Content
                               │
                               ▼
                    ┌──────────────────────┐
                    │    WRITER AGENT      │
                    │                      │
                    │      Groq LLM        │
                    └──────────┬───────────┘
                               │
                         Research Report
                               │
                               ▼
                    ┌──────────────────────┐
                    │    CRITIC AGENT      │
                    │                      │
                    │ Quality Evaluation   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    FINAL OUTPUT      │
                    │                      │
                    │ Report + Critique    │
                    └──────────────────────┘
</pre>

<hr>

<h2>🔄 Complete Project Flow — From Start to End</h2>

<h3>1️⃣ User Provides a Research Topic</h3>

<p>
The workflow starts when the user enters a research topic through the
Streamlit interface.
</p>

<p>Example:</p>

<pre>
"The impact of quantum computing on cryptography"
</pre>

<p>
The application validates that the user has entered a topic and that
the required API keys are available before starting the pipeline.
</p>

<hr>

<h3>2️⃣ Application Initializes the AI Components</h3>

<p>
The application loads the environment variables and initializes the
required services.
</p>

<ul>
  <li><strong>Groq</strong> → Large Language Model</li>
  <li><strong>Tavily</strong> → Web search</li>
  <li><strong>LangChain</strong> → Agent and chain orchestration</li>
  <li><strong>BeautifulSoup</strong> → Web-page content extraction</li>
  <li><strong>Streamlit</strong> → User interface</li>
</ul>

<p>
The LLM and Tavily clients are cached using Streamlit resources so they
do not need to be unnecessarily recreated on every interaction.
</p>

<hr>

<h3>3️⃣ Search Agent 🔍</h3>

<p>
The first specialized agent is the <strong>Search Agent</strong>.
Its responsibility is to gather recent and reliable information about
the user's topic.
</p>

<p>
The Search Agent receives a natural-language instruction and can use the
Tavily search tool.
</p>

<pre>
User Topic
    ↓
Search Agent
    ↓
Tavily
    ↓
Web Search
    ↓
Titles + URLs + Snippets
</pre>

<p>
The system collects multiple search results instead of relying on a
single webpage.
</p>

<hr>

<h3>4️⃣ Reader Agent 📖</h3>

<p>
After gathering search results, the system passes the relevant
information to the <strong>Reader Agent</strong>.
</p>

<p>
The Reader Agent identifies a relevant URL and uses the scraping tool
to retrieve deeper information from the selected webpage.
</p>

<pre>
Search Results
      ↓
Reader Agent
      ↓
Select Relevant URL
      ↓
HTTP Request
      ↓
BeautifulSoup
      ↓
Clean Web Content
</pre>

<p>
The scraper removes elements such as scripts, styles, navigation and
footer content before extracting the readable page text.
</p>

<hr>

<h3>5️⃣ Research State is Created 🧠</h3>

<p>
The system stores the gathered information in an internal state.
The state contains the search results and the scraped content.
</p>

<pre>
state = {

    "search_results": "...",

    "scraped_content": "...",

    "report": "...",

    "feedback": "..."

}
</pre>

<p>
This allows information generated at earlier stages to be passed into
the following stages of the pipeline.
</p>

<hr>

<h3>6️⃣ Writer Agent ✍️</h3>

<p>
The Writer stage combines the gathered research into a structured
research report.
</p>

<p>
The Writer receives:</p>

<ul>
  <li>The original research topic</li>
  <li>Search results</li>
  <li>Detailed scraped content</li>
</ul>

<p>
The prompt instructs the model to produce a professional report
containing:
</p>

<ul>
  <li>Introduction</li>
  <li>Key Findings</li>
  <li>Conclusion</li>
  <li>Sources</li>
</ul>

<pre>
Topic
  +
Search Results
  +
Scraped Content
       ↓
   Writer LLM
       ↓
Research Report
</pre>

<hr>

<h3>7️⃣ Critic Agent 🧐</h3>

<p>
The generated report is then passed to a separate
<strong>Critic Agent</strong>.
</p>

<p>
The Critic does not generate the original report. Instead, its role is
to evaluate the quality of the generated research.
</p>

<p>The critic evaluates:</p>

<ul>
  <li>Overall quality</li>
  <li>Strengths</li>
  <li>Areas for improvement</li>
  <li>Overall verdict</li>
</ul>

<p>
The output follows a structured evaluation format containing a score
out of 10, strengths, improvement areas and a final verdict.
</p>

<pre>
Research Report
      ↓
Critic Agent
      ↓
Quality Evaluation
      ↓
Score + Strengths + Improvements
</pre>

<hr>

<h3>8️⃣ Final Results 🎯</h3>

<p>
Once the pipeline completes, Streamlit displays the results in three
separate sections.
</p>

<table>
<tr>
<th>Section</th>
<th>Purpose</th>
</tr>

<tr>
<td>📝 Report</td>
<td>Displays the generated research report.</td>
</tr>

<tr>
<td>🧐 Critique</td>
<td>Displays the critic's evaluation.</td>
</tr>

<tr>
<td>🔬 Raw Research</td>
<td>Displays the original search results and scraped content.</td>
</tr>
</table>

<p>
The generated report can also be downloaded as a Markdown file.
</p>

<hr>

<h2>🛠️ Technology Stack</h2>

<table>
<tr>
<th>Technology</th>
<th>Purpose</th>
</tr>

<tr>
<td>Python</td>
<td>Core programming language</td>
</tr>

<tr>
<td>LangChain</td>
<td>Agents, tools and LLM orchestration</td>
</tr>

<tr>
<td>LangChain Agents</td>
<td>Specialized agent execution</td>
</tr>

<tr>
<td>Groq</td>
<td>LLM inference</td>
</tr>

<tr>
<td>Tavily</td>
<td>Web search and research retrieval</td>
</tr>

<tr>
<td>BeautifulSoup</td>
<td>Web scraping and content extraction</td>
</tr>

<tr>
<td>Requests</td>
<td>HTTP requests</td>
</tr>

<tr>
<td>Streamlit</td>
<td>Interactive web application</td>
</tr>

<tr>
<td>python-dotenv</td>
<td>Environment variable management</td>
</tr>
</table>

<hr>

<h2>📂 Project Structure</h2>

<pre>
Multi-Agent-Research-System/
│
├── app.py
│
├── requirements.txt
│
├── .env
│
└── README.md
</pre>

<hr>

<h2>⚙️ Installation</h2>

<h3>1. Clone the repository</h3>

<pre>
git clone YOUR_GITHUB_REPOSITORY_URL
cd Multi-Agent-Research-System
</pre>

<h3>2. Create a virtual environment</h3>

<pre>
python -m venv venv
</pre>

<h3>3. Activate the environment</h3>

<p><strong>Windows:</strong></p>

<pre>
venv\Scripts\activate
</pre>

<p><strong>Linux / macOS:</strong></p>

<pre>
source venv/bin/activate
</pre>

<h3>4. Install dependencies</h3>

<pre>
pip install -r requirements.txt
</pre>

<p>
The project dependencies include LangChain, LangChain Community,
LangChain Groq, Tavily, BeautifulSoup, python-dotenv and Requests.
</p>

<hr>

<h2>🔐 API Keys</h2>

<p>
Create a <code>.env</code> file in the project directory.
</p>

<pre>
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
</pre>

<p>
Never commit your real API keys to GitHub.
</p>

<hr>

<h2>▶️ Run the Application</h2>

<pre>
streamlit run app.py
</pre>

<p>
Then open the Streamlit URL displayed in your terminal.
</p>

<hr>

<h2>💡 Example Workflow</h2>

<pre>
Input:
"Impact of Artificial Intelligence on Healthcare"

                ↓

🔍 Search Agent
Finds relevant web information

                ↓

📖 Reader Agent
Selects and reads a relevant source

                ↓

✍️ Writer
Creates structured research report

                ↓

🧐 Critic
Evaluates report quality

                ↓

📄 Final Research Report
+
📊 Critique
+
🔬 Raw Research
</pre>

<hr>

<h2>✨ Key Features</h2>

<ul>
  <li>🤖 Multi-agent architecture</li>
  <li>🔍 Real-time web research</li>
  <li>🌐 Tavily-powered search</li>
  <li>📖 Automated webpage reading</li>
  <li>✍️ AI-generated structured reports</li>
  <li>🧐 Independent report criticism</li>
  <li>🔐 Secure API-key input</li>
  <li>⚡ Cached LLM and Tavily resources</li>
  <li>📥 Markdown report download</li>
  <li>🎨 Interactive Streamlit interface</li>
</ul>

<hr>

<h2>🎓 What This Project Demonstrates</h2>

<p>
This project demonstrates practical knowledge of modern
<strong>Agentic AI engineering</strong>, including:
</p>

<ul>
  <li>LLM integration</li>
  <li>Agent creation</li>
  <li>Tool calling</li>
  <li>Web search integration</li>
  <li>Web scraping</li>
  <li>Prompt engineering</li>
  <li>Chain composition</li>
  <li>Multi-step AI workflows</li>
  <li>AI-generated content evaluation</li>
  <li>Streamlit application development</li>
</ul>

<hr>

<h2>🚧 Future Improvements</h2>

<p>
The current architecture can be extended into a more advanced
production-grade research agent.
</p>

<ul>
  <li>🔄 Add Writer → Critic → Writer revision loops</li>
  <li>⚡ Run multiple research agents in parallel</li>
  <li>🧠 Use LangGraph for advanced state management</li>
  <li>✅ Add source credibility verification</li>
  <li>📊 Add automated evaluation metrics</li>
  <li>💾 Add research history and persistent storage</li>
  <li>📚 Add document/PDF research capabilities</li>
  <li>👁️ Add observability and tracing</li>
  <li>🚀 Deploy as a production API + frontend architecture</li>
</ul>

<hr>

<h2>🏆 Project Summary</h2>

<p>
The <strong>Multi-Agent Research System</strong> demonstrates how a
complex research task can be decomposed into multiple specialized
AI agents. Each component has a clearly defined responsibility:
searching, reading, writing and evaluating.
</p>

<p>
Instead of asking one LLM to perform the entire task, the system
creates a structured workflow where specialized components cooperate
to produce a more organized research experience.
</p>

<p align="center">
  <strong>🔍 Search → 📖 Read → ✍️ Write → 🧐 Critique → 📄 Final Report</strong>
</p>

<hr>

<h3 align="center">Built with Python • LangChain • Groq • Tavily • Streamlit</h3>
