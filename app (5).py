"""
Multi-Agent Research System — app.py
=====================================
Implements the "Enhanced Architecture" diagram:

    USER -> ORCHESTRATOR -> SEARCH AGENT -> READER AGENT -> WRITER CHAIN
            -> CRITIC CHAIN (revision loop back to WRITER) -> OUTPUT (UI)

Cross-cutting: Source Metadata & Citation Store, Structured Logging,
Error Handling & Retry, Validation (Pydantic), Revision Loop (1-2 cycles).

This file is a from-scratch, working rewrite of the original research
notebook. Every function below is commented with what it does and, where
relevant, which bug from the notebook it fixes (see PROJECT_REPORT.pdf
for the full bug list).
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from tavily import TavilyClient
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate


# ---------------------------------------------------------------------------
# LOGGER  (diagram box: "Logger" / "Structured Logging")
# ---------------------------------------------------------------------------
# Every stage of the pipeline writes to this logger. In the Streamlit UI the
# same messages are also collected into `state.logs` so they can be shown to
# the user under the "Logs" tab.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("research_system")

load_dotenv()  # reads GROQ_API_KEY / TAVILY_API_KEY from a local .env file


# ---------------------------------------------------------------------------
# STRUCTURED OUTPUT SCHEMAS  (diagram: "Structured Output (JSON)" boxes)
# ---------------------------------------------------------------------------
# These Pydantic models are what force every LLM stage to return clean,
# validated JSON instead of free-form text. This is also the "Validation"
# box under Logging & Error Handling in the diagram.

class SearchResult(BaseModel):
    """One hit returned by the Search Agent."""
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None


class SearchOutput(BaseModel):
    """Full structured output of Stage 1 (Search Agent)."""
    query: str
    results: List[SearchResult] = Field(default_factory=list)


class ReaderOutput(BaseModel):
    """Full structured output of Stage 2 (Reader Agent)."""
    url: str
    title: str
    clean_text: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)
    fetched_at: str


class WriterSections(BaseModel):
    introduction: str
    key_findings: List[str] = Field(default_factory=list)
    conclusion: str


class Citation(BaseModel):
    title: str
    url: str


class WriterOutput(BaseModel):
    """Full structured output of Stage 3 (Writer Chain)."""
    report: str
    sections: WriterSections
    citations: List[Citation] = Field(default_factory=list)


class CriticOutput(BaseModel):
    """Full structured output of Stage 4 (Critic Chain)."""
    score: int = Field(ge=0, le=10)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    feedback: str
    improvements: List[str] = Field(default_factory=list)   # fixed typo "improvments"
    citations_check: str      # "valid" | "missing"
    hallucination_risk: str   # "low" | "medium" | "high"


# ---------------------------------------------------------------------------
# SOURCE METADATA & CITATION STORE  (diagram: "Source Metadata & Citation Store")
# ---------------------------------------------------------------------------
class CitationStore:
    """
    Shared store that every stage writes into, so citations from the very
    first search hit still show up in the final report. Deduplicates by URL,
    exactly as the diagram's schema describes:
    {title, url, source, fetched_at, snippet, used_in}
    """

    def __init__(self):
        self._sources: Dict[str, dict] = {}

    def add(self, url: str, title: str = "", source: str = "", snippet: str = "", used_in: str = ""):
        """Add or merge one source. Safe to call repeatedly with the same URL."""
        if not url:
            return
        if url in self._sources:
            existing = self._sources[url]
            if used_in and used_in not in existing["used_in"]:
                existing["used_in"].append(used_in)
            return
        self._sources[url] = {
            "title": title,
            "url": url,
            "source": source,
            "fetched_at": datetime.utcnow().isoformat(),
            "snippet": snippet,
            "used_in": [used_in] if used_in else [],
        }

    def add_search_results(self, search_output: SearchOutput):
        """Bulk-add every result from a Search Agent run."""
        for r in search_output.results:
            self.add(r.url, title=r.title, source="search", snippet=r.snippet, used_in="search")

    def add_reader_result(self, reader_output: ReaderOutput):
        """Add the single page the Reader Agent scraped."""
        self.add(reader_output.url, title=reader_output.title, source="reader",
                  snippet=reader_output.summary, used_in="reader")

    def get_all(self) -> List[dict]:
        return list(self._sources.values())


# ---------------------------------------------------------------------------
# ERROR HANDLING & RETRY  (diagram: "Error Handler & Retry")
# ---------------------------------------------------------------------------
def with_retry(fn, *args, retries: int = 3, backoff: float = 1.5, label: str = "call", **kwargs):
    """
    Runs fn(*args, **kwargs). On exception, logs a warning and retries with
    exponential backoff (1.5s, 2.25s, ...). Raises the last error if every
    attempt fails, so the caller can show it to the user instead of crashing
    silently. This wraps every network / LLM call in the pipeline.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            logger.warning("Attempt %s/%s failed for %s: %s", attempt, retries, label, e)
            if attempt < retries:
                time.sleep(backoff ** attempt)
    logger.error("All %s attempts failed for %s: %s", retries, label, last_err)
    raise last_err


# ---------------------------------------------------------------------------
# LLM / TOOL CLIENTS
# ---------------------------------------------------------------------------
@st.cache_resource
def get_clients(model_name: str):
    """Build (and cache) the Groq LLM client and the Tavily search client."""
    llm = ChatGroq(model=model_name, temperature=0)  # fixed typo: temprature -> temperature
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return llm, tavily


def web_search(tavily: TavilyClient, query: str, max_results: int = 5) -> List[dict]:
    """
    Search the web through Tavily and return the raw list of result dicts
    (title/url/content/published_date). Fixed: the old code passed
    `max_result` (no "s"), which Tavily's API silently ignored.
    """
    result = tavily.search(query=query, max_results=max_results)
    return result.get("results", [])


def scrape_url(url: str, char_limit: int = 3000) -> str:
    """
    Download a page and return its clean visible text, stripped of
    script/style/nav/footer/header noise. Used by the Reader Agent.
    """
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()  # fixed: old code wrote `tag.decompose` with no "()", so nothing was removed
        return soup.get_text(separator=" ", strip=True)[:char_limit]
    except Exception as e:
        logger.warning("Scrape failed for %s: %s", url, e)
        return f"Could not scrape URL: {e}"


# ---------------------------------------------------------------------------
# STAGE 1 — SEARCH AGENT
# ---------------------------------------------------------------------------
def run_search_agent(llm, tavily, topic: str) -> SearchOutput:
    """
    Search the web for the topic, then ask the LLM to reshape the raw
    Tavily results into the validated SearchOutput schema.
    """
    logger.info("STEP 1: Search agent searching for '%s'", topic)
    raw_results = with_retry(web_search, tavily, topic, label="tavily_search")

    structured_llm = llm.with_structured_output(SearchOutput)
    prompt = f"""Convert the following raw web search results into the required structured format.

User query: {topic}

Raw results (JSON):
{json.dumps(raw_results)[:6000]}

Rules:
- Only use information present in the raw results above.
- Do not invent URLs, titles, or dates.
- If a published date is unavailable, leave it null.
"""
    output = with_retry(structured_llm.invoke, prompt, label="search_format")
    if not isinstance(output, SearchOutput):
        output = SearchOutput.model_validate(output)
    output.query = topic
    return output


# ---------------------------------------------------------------------------
# STAGE 2 — READER AGENT
# ---------------------------------------------------------------------------
def run_reader_agent(llm, search_output: SearchOutput) -> Optional[ReaderOutput]:
    """
    Scrape the top search result and ask the LLM to turn the scraped page
    into the validated ReaderOutput schema (summary + key points).
    """
    if not search_output.results:
        logger.warning("No search results to read")
        return None

    top_result = search_output.results[0]
    logger.info("STEP 2: Reader agent scraping %s", top_result.url)
    scraped_text = with_retry(scrape_url, top_result.url, label="scrape_url")

    structured_llm = llm.with_structured_output(ReaderOutput)
    prompt = f"""Convert the following scraped page content into the required structured format.

Source URL: {top_result.url}
Source Title: {top_result.title}

Scraped content:
{scraped_text}

Rules:
- Preserve the source URL exactly as given.
- Write a concise summary (3-5 sentences).
- Extract 3-6 key points as a list.
- Put any extra source info (author, domain, etc.) in metadata.
- Do not invent information that is not present in the scraped content.
"""
    output = with_retry(structured_llm.invoke, prompt, label="reader_format")
    if not isinstance(output, ReaderOutput):
        output = ReaderOutput.model_validate(output)
    output.url = top_result.url
    output.fetched_at = datetime.utcnow().isoformat()
    return output


# ---------------------------------------------------------------------------
# STAGE 3 — WRITER CHAIN
# ---------------------------------------------------------------------------
WRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research gathered:
{research}

{revision_note}

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Citations (title + url for every source actually used)

Be detailed, factual and professional."""),
])


def run_writer_chain(llm, topic: str, research_combined: str, feedback: str = "") -> WriterOutput:
    """
    Draft (or re-draft, if `feedback` is non-empty) the research report as a
    validated WriterOutput. `feedback` is how the Critic Chain's notes get
    fed back in on a revision loop iteration.
    """
    logger.info("STEP 3: Writer chain drafting report%s", " (revision)" if feedback else "")
    structured_llm = llm.with_structured_output(WriterOutput)
    revision_note = f"Address this feedback from the previous review:\n{feedback}" if feedback else ""
    chain = WRITER_PROMPT | structured_llm
    output = with_retry(
        chain.invoke,
        {"topic": topic, "research": research_combined, "revision_note": revision_note},
        label="writer_chain",
    )
    if not isinstance(output, WriterOutput):
        output = WriterOutput.model_validate(output)
    return output


# ---------------------------------------------------------------------------
# STAGE 4 — CRITIC CHAIN
# ---------------------------------------------------------------------------
CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Score it 0-10, list concrete strengths and weaknesses, give concrete
improvements, say whether citations are "valid" or "missing", and rate the
hallucination risk as "low", "medium" or "high"."""),
])


def run_critic_chain(llm, report_text: str) -> CriticOutput:
    """Ask the LLM to critique the written report and return a validated CriticOutput."""
    logger.info("STEP 4: Critic chain reviewing report")
    structured_llm = llm.with_structured_output(CriticOutput)
    chain = CRITIC_PROMPT | structured_llm
    output = with_retry(chain.invoke, {"report": report_text}, label="critic_chain")
    if not isinstance(output, CriticOutput):
        output = CriticOutput.model_validate(output)
    return output


# ---------------------------------------------------------------------------
# ORCHESTRATOR / SHARED STATE  (diagram: whole purple "Orchestrator" box)
# ---------------------------------------------------------------------------
class ResearchState(BaseModel):
    """Shared state object the orchestrator passes through every stage."""
    model_config = ConfigDict(arbitrary_types_allowed=True)  # fixed: was the wrong attr name `config_model`

    topic: str
    search_result: Optional[SearchOutput] = None
    reader_result: Optional[ReaderOutput] = None
    writer_result: Optional[WriterOutput] = None
    critic_result: Optional[CriticOutput] = None
    citation_store: CitationStore
    revision_count: int = 0
    max_revisions: int = 2
    score_threshold: int = 7
    logs: List[str] = Field(default_factory=list)

    def log(self, msg: str):
        self.logs.append(msg)
        logger.info(msg)


def run_research_pipeline(
    topic: str,
    model_name: str = "llama-3.3-70b-versatile",
    max_revisions: int = 2,
    score_threshold: int = 7,
) -> ResearchState:
    """
    The Orchestrator. Runs Search -> Reader -> Writer -> Critic, then loops
    Writer <-> Critic (the diagram's "Revision Loop") until the critic score
    clears score_threshold or max_revisions is hit ("final approval" box).
    """
    llm, tavily = get_clients(model_name)
    state = ResearchState(
        topic=topic,
        citation_store=CitationStore(),
        max_revisions=max_revisions,
        score_threshold=score_threshold,
    )

    # --- Stage 1: Search ---
    state.log(f"Step 1/4: searching for '{topic}'")
    state.search_result = run_search_agent(llm, tavily, topic)
    state.citation_store.add_search_results(state.search_result)

    # --- Stage 2: Read ---
    state.log("Step 2/4: reading top source")
    state.reader_result = run_reader_agent(llm, state.search_result)
    if state.reader_result:
        state.citation_store.add_reader_result(state.reader_result)

    # --- Build the combined research context passed to the writer ---
    search_summary = "\n".join(
        f"- {r.title} ({r.url}): {r.snippet}" for r in state.search_result.results
    )
    reader_summary = ""
    if state.reader_result:
        reader_summary = (
            f"\nDetailed source ({state.reader_result.url}):\n"
            f"Summary: {state.reader_result.summary}\n"
            f"Key points: {', '.join(state.reader_result.key_points)}"
        )
    research_combined = f"SEARCH RESULTS:\n{search_summary}\n{reader_summary}"

    # --- Stage 3: first draft ---
    state.log("Step 3/4: drafting report")
    state.writer_result = run_writer_chain(llm, topic, research_combined)
    for c in state.writer_result.citations:
        state.citation_store.add(c.url, title=c.title, source="writer", used_in="writer")

    # --- Stage 4: first critique ---
    state.log("Step 4/4: critic reviewing report")
    state.critic_result = run_critic_chain(llm, state.writer_result.report)

    # --- Revision loop (this loop did not exist at all in the original code) ---
    while (
        state.critic_result.score < state.score_threshold
        and state.revision_count < state.max_revisions
    ):
        state.revision_count += 1
        state.log(
            f"Revision loop {state.revision_count}/{state.max_revisions}: "
            f"score {state.critic_result.score} < threshold {state.score_threshold}, rewriting"
        )
        feedback_text = state.critic_result.feedback + "\n" + "\n".join(
            f"- {imp}" for imp in state.critic_result.improvements
        )
        state.writer_result = run_writer_chain(llm, topic, research_combined, feedback_text)
        for c in state.writer_result.citations:
            state.citation_store.add(c.url, title=c.title, source="writer", used_in="writer")
        state.critic_result = run_critic_chain(llm, state.writer_result.report)

    state.log(
        f"Done. Final score {state.critic_result.score}/10 after "
        f"{state.revision_count} revision(s)"
    )
    return state


# ---------------------------------------------------------------------------
# STREAMLIT UI  (diagram: "USER (Streamlit UI)" + "OUTPUT (UI)")
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Multi-Agent Research System", page_icon="🔎", layout="wide")
    st.title("🔎 Multi-Agent Research System")
    st.caption("Search Agent → Reader Agent → Writer Chain → Critic Chain (with Revision Loop)")

    with st.sidebar:
        st.header("Settings")
        model_name = st.selectbox(
            "Groq model",
            ["llama-3.3-70b-versatile", "llama-3.1-8b-instant","Qwen 3.6 27B"],
            index=0,
        )
        max_revisions = st.slider("Max revision cycles", 0, 3, 2)
        score_threshold = st.slider("Approval score threshold", 0, 10, 7)
        st.divider()
        st.caption("Requires GROQ_API_KEY and TAVILY_API_KEY in your environment or a .env file")

    topic = st.text_input("Research topic", placeholder="e.g. latest developments in agentic AI")
    run_clicked = st.button("Run research", type="primary", use_container_width=True)

    if run_clicked:
        if not topic.strip():
            st.warning("Please enter a topic.")
            return
        if not os.getenv("TAVILY_API_KEY") or not os.getenv("GROQ_API_KEY"):
            st.error("Missing TAVILY_API_KEY or GROQ_API_KEY in your environment.")
            return

        with st.status("Running pipeline...", expanded=True) as status:
            try:
                state = run_research_pipeline(
                    topic,
                    model_name=model_name,
                    max_revisions=max_revisions,
                    score_threshold=score_threshold,
                )
                for line in state.logs:
                    st.write(line)
                status.update(label="Pipeline complete", state="complete")
            except Exception as e:
                logger.exception("Pipeline failed")
                status.update(label="Pipeline failed", state="error")
                st.error(f"Something went wrong: {e}")
                return

        st.session_state["last_state"] = state

    state = st.session_state.get("last_state")
    if state:
        tab_report, tab_citations, tab_critic, tab_logs = st.tabs(
            ["📄 Final Report", "🔗 Citations", "🧐 Critic Score", "🪵 Logs"]
        )

        with tab_report:
            w = state.writer_result
            st.markdown(f"## {state.topic}")
            st.markdown("### Introduction")
            st.write(w.sections.introduction)
            st.markdown("### Key Findings")
            for kf in w.sections.key_findings:
                st.markdown(f"- {kf}")
            st.markdown("### Conclusion")
            st.write(w.sections.conclusion)

        with tab_citations:
            sources = state.citation_store.get_all()
            if not sources:
                st.info("No sources recorded.")
            for src in sources:
                st.markdown(f"- [{src['title'] or src['url']}]({src['url']})  — _{src['source']}_")

        with tab_critic:
            c = state.critic_result
            st.metric("Score", f"{c.score}/10")
            st.write("**Strengths**")
            for s in c.strengths:
                st.markdown(f"- {s}")
            st.write("**Weaknesses**")
            for wk in c.weaknesses:
                st.markdown(f"- {wk}")
            st.write(f"**Citations check:** {c.citations_check}")
            st.write(f"**Hallucination risk:** {c.hallucination_risk}")
            st.write(f"**Revisions used:** {state.revision_count}/{state.max_revisions}")

        with tab_logs:
            for line in state.logs:
                st.text(line)


if __name__ == "__main__":
    main()
