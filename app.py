"""
Multi-Agent Research System — Streamlit App
Pipeline: Search Agent -> Reader Agent -> Writer Chain -> Critic Chain

This is a bug-fixed, Streamlit-wrapped version of the original notebook.
Logic and pipeline design are unchanged — only bugs were fixed and a UI was added.
"""

import os
import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tavily import TavilyClient

load_dotenv()

# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Multi-Agent Research System",
    page_icon="🔎",
    layout="wide",
)

# --------------------------------------------------------------------------
# Sidebar — API keys & settings
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Settings")

    groq_key_default = os.getenv("GROQ_API_KEY", "")
    tavily_key_default = os.getenv("TAVILY_API_KEY", "")

    groq_api_key = st.text_input(
        "Groq API Key", value=groq_key_default, type="password",
        help="Get one at console.groq.com"
    )
    tavily_api_key = st.text_input(
        "Tavily API Key", value=tavily_key_default, type="password",
        help="Get one at tavily.com"
    )

    st.divider()
    model_name = st.selectbox(
        "Groq model",
        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        index=0,
    )
    max_search_results = st.slider("Max search results", 3, 10, 5)

    st.divider()
    st.caption(
        "Pipeline: 🔍 Search Agent → 📖 Reader Agent → ✍️ Writer → 🧐 Critic"
    )

# --------------------------------------------------------------------------
# Cached resources (LLM + Tavily client) — rebuilt only when keys change
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_llm(api_key: str, model: str):
    return ChatGroq(model=model, api_key=api_key, temperature=0)  # fixed: "temprature" typo


@st.cache_resource(show_spinner=False)
def get_tavily(api_key: str):
    return TavilyClient(api_key=api_key)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
def make_web_search_tool(tavily_client, max_results: int):
    @tool
    def web_search(query: str) -> str:
        """Search the web for recent and reliable information on a topic. Returns titles, URLs and snippets."""
        result = tavily_client.search(query=query, max_results=max_results)  # fixed: "max_result" -> "max_results"

        out = []
        for r in result["results"]:
            out.append(
                f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n"
            )
        return "\n---\n".join(out)  # fixed: return was inside the loop, only ever returning 1 result

    return web_search


@tool
def scrap_url(url: str) -> str:
    """Scrape and return clean text content from a given URL for deeper reading."""
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()  # fixed: was missing "()", so tags were never actually removed

        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as e:
        return f"Could not scrape URL: {str(e)}"


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------
def build_search_agent(llm, web_search_tool):
    return create_agent(model=llm, tools=[web_search_tool])


def build_reader_agent(llm):
    return create_agent(model=llm, tools=[scrap_url])  # fixed: "scarp_url" (undefined name) -> "scrap_url"


# --------------------------------------------------------------------------
# Writer & Critic chains
# --------------------------------------------------------------------------
def build_writer_chain(llm):
    writer_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
        ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Sources (list all URLs found in the research)

Be detailed, factual and professional."""),
    ])  # fixed: original list was malformed (missing opening "(" on first tuple)

    return writer_prompt | llm | StrOutputParser()  # fixed: StrOutputParser was never instantiated


def build_critic_chain(llm):
    critic_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a sharp and constructive research critic. Be honest and specific."),
        ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
    ])  # fixed: same malformed-tuple bug as writer_prompt

    return critic_prompt | llm | StrOutputParser()  # fixed: StrOutputParser was never instantiated


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def run_research_pipeline(topic: str, llm, tavily_client, max_results: int, status_cb=None):
    """
    Fixed version of the original run_resarch_pipline function.

    Bugs fixed:
      - state[search_result] -> state["search_results"]  (was using an undefined variable as a dict key)
      - messages": [...] -> "messages": [...]              (missing opening quote, syntax error)
      - state[scarped_content] -> state["scraped_content"]  (undefined variable as dict key + typo)
      - writer_chain.invoke key "research_combined" -> "research" (didn't match the prompt's {research} placeholder)
      - run_research_pipeline(topic) call referenced a function name that didn't match its definition
    """
    state = {}

    def log(msg):
        if status_cb:
            status_cb(msg)

    # Step 1: Search
    log("🔍 Search agent is gathering information...")
    web_search_tool = make_web_search_tool(tavily_client, max_results)
    search_agent = build_search_agent(llm, web_search_tool)
    search_result = search_agent.invoke({
        "messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]
    })
    state["search_results"] = search_result["messages"][-1].content

    # Step 2: Read / scrape
    log("📖 Reader agent is scraping the top resource...")
    reader_agent = build_reader_agent(llm)
    reader_result = reader_agent.invoke({
        "messages": [(
            "user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    })
    state["scraped_content"] = reader_result["messages"][-1].content

    # Step 3: Write
    log("✍️ Writer is drafting the report...")
    research_combined = (
        f"SEARCH RESULTS:\n{state['search_results']}\n\n"
        f"DETAILED SCRAPED CONTENT:\n{state['scraped_content']}"
    )
    writer_chain = build_writer_chain(llm)
    state["report"] = writer_chain.invoke({
        "topic": topic,
        "research": research_combined,  # fixed: key now matches {research} in the prompt template
    })

    # Step 4: Critique
    log("🧐 Critic is reviewing the report...")
    critic_chain = build_critic_chain(llm)
    state["feedback"] = critic_chain.invoke({
        "report": state["report"]
    })

    return state


# --------------------------------------------------------------------------
# Main UI
# --------------------------------------------------------------------------
st.title("🔎 Multi-Agent Research System")
st.caption("Search → Read → Write → Critique — powered by Groq + Tavily + LangChain agents")

topic = st.text_input(
    "Research topic",
    placeholder="e.g. The impact of quantum computing on cryptography",
)

col1, col2 = st.columns([1, 5])
with col1:
    run_clicked = st.button("🚀 Start Research", type="primary", use_container_width=True)

if run_clicked:
    if not groq_api_key or not tavily_api_key:
        st.error("Please add your Groq and Tavily API keys in the sidebar first.")
    elif not topic.strip():
        st.error("Please enter a research topic.")
    else:
        llm = get_llm(groq_api_key, model_name)
        tavily_client = get_tavily(tavily_api_key)

        status_box = st.status("Starting research pipeline...", expanded=True)

        def status_cb(msg):
            status_box.write(msg)

        try:
            result = run_research_pipeline(
                topic=topic,
                llm=llm,
                tavily_client=tavily_client,
                max_results=max_search_results,
                status_cb=status_cb,
            )
            status_box.update(label="✅ Research complete!", state="complete", expanded=False)

            st.session_state["last_result"] = result
            st.session_state["last_topic"] = topic

        except Exception as e:
            status_box.update(label="❌ Pipeline failed", state="error", expanded=True)
            st.error(f"Something went wrong: {e}")

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    topic_done = st.session_state["last_topic"]

    st.divider()
    st.subheader(f"📄 Results for: {topic_done}")

    report_tab, critique_tab, sources_tab = st.tabs(["📝 Report", "🧐 Critique", "🔬 Raw Research"])

    with report_tab:
        st.markdown(result["report"])
        st.download_button(
            "⬇️ Download report (.md)",
            data=result["report"],
            file_name=f"{topic_done.replace(' ', '_')}_report.md",
            mime="text/markdown",
        )

    with critique_tab:
        st.markdown(result["feedback"])

    with sources_tab:
        with st.expander("Search results", expanded=False):
            st.text(result["search_results"])
        with st.expander("Scraped content", expanded=False):
            st.text(result["scraped_content"])
else:
    st.info("Enter a topic and click **Start Research** to run the pipeline.")
