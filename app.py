import os
from typing import TypedDict, List
import streamlit as st

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq 
from pydantic import BaseModel  
from tavily import TavilyClient
from langgraph.checkpoint.memory import MemorySaver

# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(page_title="AI Automated Essay Writer", layout="wide", page_icon="📝")
st.title("📝 AI Automated Essay Writer")
st.markdown("An autonomous agent workflow that plans, researches, drafts, and reflects to write a high-quality essay.")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("Configuration")
st.sidebar.info("The application allows exactly 1 interactive revision stage based on the teacher's critique feedback.")

# --- SECRETS VALIDATION ---
if "GROQ_API_KEY" not in st.secrets or "TAVILY_API_KEY" not in st.secrets:
    st.error("⚠️ **Missing API Keys in Secrets!**")
    st.markdown("""
    Please create a folder named `.streamlit` in your project root directory, and inside it, 
    create a file named `secrets.toml` with your keys:
    
    ```toml
    GROQ_API_KEY = "your-groq-api-key-here"
    TAVILY_API_KEY = "your-tavily-api-key-here"
    ```
    """)
    st.stop()

# Inject secrets directly into environment variables
os.environ['GROQ_API_KEY'] = st.secrets["GROQ_API_KEY"]
os.environ['TAVILY_API_KEY'] = st.secrets["TAVILY_API_KEY"]

# --- STREAMLIT SESSION STATE INITIALIZATION ---
if "history" not in st.session_state:
    st.session_state.history = []  
if "revision_status" not in st.session_state:
    st.session_state.revision_status = "none"  # "none", "prompting", "executed", "declined"
if "graph_active" not in st.session_state:
    st.session_state.graph_active = False  
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()  
if "current_task" not in st.session_state:
    st.session_state.current_task = ""

# --- DEFINITIONS & AGENT PROMPTS ---

class AgentState(TypedDict):
    task: str
    plan: str
    draft: str
    critique: str
    content: List[str]
    revision_number: int
    max_revisions: int

PLAN_PROMPT = '''You are an expert writer tasked with writing a high level outline of an essay.
Write such an outline for the user provided topic.
Give an outline of the essay along with any relevant notes or instructions for the sections.'''

RESEARCH_PLAN_PROMPT = '''You are a researcher charged with providing information that can be used when writing the following essay.
Generate a list of search queries that will gather any relevant information. Only generate 3 queries max.'''

WRITER_PROMPT = '''You are an essay assistant tasked with writing excellent 5-paragraph essays.
Generate the best essay possible for the user's request and the initial outline.
If the user provides critique, respond with a revised version of your previous attempts.
Utilize all the information below as needed: 

------

{content}'''

REFLECTION_PROMPT = '''You are a teacher grading an essay submission.
Generate critique and recommendations for the user's submission.
Provide detailed recommendations, including requests for length, depth, style, etc.'''

RESEARCH_CRITIQUE_PROMPT = ''''You are a researcher charged with providing information that can \
be used when making any requested revisions (as outlined below).
Generate a list of search queries that will gather any relevant information. Only generate 3 queries max.'''

class Queries(BaseModel):
    queries: List[str]

# --- CONDITIONAL EDGE FUNCTION ---
def should_continue(state: AgentState):
    # max_revisions is hardcoded to 2. 
    # Run 1: revision_number becomes 2 -> 2 > 2 is False -> goes to 'reflect'
    # Run 2: revision_number becomes 3 -> 3 > 2 is True -> goes to END
    if state.get("revision_number", 1) > state.get("max_revisions", 2):
        return END
    return "reflect"

# --- MAIN APPLICATION LOGIC ---

# Dynamic Bot Greeting based on current workflow status
with st.chat_message("assistant"):
    if st.session_state.revision_status in ["executed", "declined"]:
        st.write("🔄 We have finalized this essay session! If you would like to generate another essay, please enter a new topic below.")
    elif st.session_state.revision_status == "prompting":
        st.write("📋 I've generated the initial essay and compiled the teacher's critique. Review them below and let me know if you want a revision!")
    else:
        st.write("👋 Hello! I am your AI Essay Writer. What topic would you like me to write an essay about today?")

# Manual user input for the topic
task = st.text_input("Enter Essay Topic Here:", value="", placeholder="e.g., Nvidia Blackwell AI chip, Quantum Computing, etc.")

if st.button("Generate Essay", type="primary"):
    if not task.strip():
        st.warning("Please provide an essay topic first!")
    else:
        # Reset parameters completely for a clean new session
        st.session_state.history = []
        st.session_state.revision_status = "none"
        st.session_state.memory = MemorySaver()  
        st.session_state.current_task = task
        st.session_state.graph_active = True
        st.rerun()

# --- HELPER RENDERING FUNCTION ---
def render_event(e):
    if 'planner' in e:
        with st.expander("Phase 1: Essay Plan Outline Generated", expanded=False):
            st.write(e['planner']['plan'])
    elif 'research_plan' in e:
        with st.expander("Phase 2: Core Research Gathering Complete", expanded=False):
            st.success(f"Gathered {len(e['research_plan']['content'])} reference snippets.")
    elif 'generate' in e:
        rev_num = e['generate']['revision_number'] - 1
        with st.expander(f"Phase 3: Essay Draft Formed (Revision #{rev_num})", expanded=True):
            st.write(e['generate']['draft'])
    elif 'reflect' in e:
        with st.expander("Phase 4: Teacher's Reflection & Critique", expanded=True):
            st.write(e['reflect']['critique'])
    elif 'research_critique' in e:
        with st.expander("Phase 5: Supplementary Research via Critique Feedback", expanded=False):
            st.success("Acquired additional target references based on structural gaps.")

# Pre-render historical events so they persist across session refreshes
for past_event in st.session_state.history:
    render_event(past_event)

# --- EXECUTION LOOP (GRAPH EXECUTION AND INTERRUPTIONS) ---
if st.session_state.graph_active:
    
    model = ChatGroq(model='llama-3.3-70b-versatile', temperature=0)
    tavily = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])

    # Re-map standard nodes
    def plan_node(state: AgentState):
        messages = [SystemMessage(content=PLAN_PROMPT), HumanMessage(content=state['task'])]
        return {"plan": model.invoke(messages).content}

    def research_plan_node(state: AgentState):
        queries = model.with_structured_output(Queries).invoke([
            SystemMessage(content=RESEARCH_PLAN_PROMPT), HumanMessage(content=state['task'])
        ])
        content = state.get('content', [])
        for q in queries.queries:
            response = tavily.search(query=q, max_results=2)
            for r in response['results']: content.append(r['content'])
        return {"content": content}

    def generation_node(state: AgentState):
        content = "\n\n".join(state['content'] or [])
        user_message = HumanMessage(content=f"{state['task']}\n\nHere is my plan:\n\n{state['plan']}")
        messages = [SystemMessage(content=WRITER_PROMPT.format(content=content)), user_message]
        return {"draft": model.invoke(messages).content, "revision_number": state.get("revision_number", 1) + 1}

    def reflection_node(state: AgentState):
        messages = [SystemMessage(content=REFLECTION_PROMPT), HumanMessage(content=state['draft'])]
        return {"critique": model.invoke(messages).content}

    def research_critique_node(state: AgentState):
        queries = model.with_structured_output(Queries).invoke([
            SystemMessage(content=RESEARCH_CRITIQUE_PROMPT), HumanMessage(content=state['critique'])
        ])
        content = state['content'] or []
        for q in queries.queries:
            response = tavily.search(query=q, max_results=2)
            for r in response['results']: content.append(r['content'])
        return {'content': content}

    # Construct graph structure
    builder = StateGraph(AgentState)
    builder.add_node('planner', plan_node)
    builder.add_node('generate', generation_node)
    builder.add_node('reflect', reflection_node)
    builder.add_node('research_plan', research_plan_node)
    builder.add_node('research_critique', research_critique_node)

    builder.set_entry_point('planner')
    builder.add_conditional_edges('generate', should_continue, {END: END, 'reflect': 'reflect'})
    builder.add_edge('planner', 'research_plan')
    builder.add_edge('research_plan', 'generate')
    builder.add_edge('reflect', 'research_critique')
    builder.add_edge('research_critique', 'generate')

    # CHANGED: We now compile the checkpointer to interrupt immediately after 'reflect' (Phase 4)
    graph = builder.compile(checkpointer=st.session_state.memory, interrupt_after=['reflect'])
    thread = {'configurable': {'thread_id': '1'}}

    with st.container():
        if len(st.session_state.history) == 0:
            st.info("⚡ Executing Phases 1 through 4 (Planning, Core Research, Initial Draft, and Critique)...")
            prompt = {
                'task': st.session_state.current_task,
                'max_revisions': 2, 
                'revision_number': 1,
            }
            events = graph.stream(prompt, thread)
        else:
            st.info("⚡ Resuming workflow for Phase 5 (Critique Research) and Final Draft Generation...")
            events = graph.stream(None, thread)

        for e in events:
            st.session_state.history.append(e)
            render_event(e)
            
    # Stop the execution loop from auto-running on layout changes
    st.session_state.graph_active = False
    
    # Update state flags based on what just finished running
    if st.session_state.revision_status == "none":
        st.session_state.revision_status = "prompting"
    else:
        st.session_state.revision_status = "executed"
        
    st.rerun()

# --- HUMAN REVISION INTERACTIVE CONTROLS ---
if len(st.session_state.history) > 0 and not st.session_state.graph_active:
    
    # CASE 1: App is paused right after Phase 4 (Critique) and waiting for user input
    if st.session_state.revision_status == "prompting":
        st.markdown("---")
        st.subheader("🔁 Revision Request")
        st.write("Do you need a revision based on the teacher's reflection and critique provided above?")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, proceed with revision stage", type="primary"):
                st.session_state.graph_active = True
                st.rerun()
        with col2:
            if st.button("No, I am satisfied with this version"):
                st.session_state.revision_status = "declined"
                st.success("🎉 Final essay draft locked in successfully!")
                st.rerun()
                
    # CASE 2: The revision cycle has completed (or was declined)
    elif st.session_state.revision_status in ["executed", "declined"]:
        st.markdown("---")
        st.subheader("Final Essay Output")
        
        # Find the latest generated draft in our execution history to display cleanly at the bottom
        final_draft = ""
        for event in reversed(st.session_state.history):
            if 'generate' in event:
                final_draft = event['generate']['draft']
                break
                
        st.write(final_draft)
        st.warning("Complete workflow finished. No further revisions can be requested for this essay. Please input a new topic above if you wish to start over.")