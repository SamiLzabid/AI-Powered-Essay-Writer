# 📝 AI Automated Essay Writer (LangGraph & Streamlit)
An autonomous multi-agent essay-writing workflow that simulates the real-world writing process: outline planning, extensive web research, initial drafting, and professional academic critique, culminating in an interactive human-in-the-loop revision cycle.

Built using LangGraph for state management, Streamlit for the frontend interface, LangChain / Groq (Llama 3.3 70B) for specialized agent nodes, and Tavily AI for real-time internet search gathering.

## 🚀 Key Features
Autonomous Multi-Agent Collaboration: Divides the complex task of essay writing into distinct, specialized role-based agents (Planner, Researcher, Writer, and Teacher).

Stateful Orchestration: Utilizes LangGraph to pass context dynamically between agents while avoiding infinite loops.

Human-in-the-Loop Interruption: Automatically pauses execution after Phase 4 (Teacher's Critique), allowing users to review the initial output and explicitly opt-in or out of a revision stage.

Strict Single-Revision Cap: Built-in safeguards allow exactly one advanced structural revision session based on user consent before automatically freezing outputs and resetting for a new topic.

Persistent Session Cache: Implements LangGraph’s MemorySaver checkpointer ensuring historical states persist gracefully across Streamlit's structural reruns.

## 🔬 Agent Architecture & Workflow
The system progresses through a highly structured 5-Phase architecture:
```mermaid
graph TB
    %% Professional Color Palette & Styling
    classDef default fill:#f8f9fa,stroke:#ced4da,stroke-width:1px,color:#212529;
    classDef inputOutput fill:#e9ecef,stroke:#6c757d,stroke-width:2px,color:#212529;
    classDef process fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px,color:#0d47a1;
    classDef interrupt fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100,stroke-dasharray: 5 5;
    classDef decision fill:#e8f5e9,stroke:#43a047,stroke-width:2px,color:#1b5e20;
    classDef final fill:#1e88e5,stroke:#0d47a1,stroke-width:2px,color:#ffffff;

    %% Entry Point
    START([📥 User Input: Essay Topic]):::inputOutput
    
    %% First Block: Generation
    subgraph Core_Workflow [Initial Generation Workflow]
        direction TB
        P1(Phase 1: Planner Node<br/>Generates Outline):::process
        P2(Phase 2: Research Plan<br/>Core Web Scraping):::process
        P3(Phase 3: Generation<br/>Drafts Initial Essay):::process
        P4(Phase 4: Reflection<br/>Teacher Critique):::process
        
        P1 --> P2 --> P3 --> P4
    end

    %% Human in the loop
    INTERRUPT{{LangGraph Interrupt<br/>Pauses for Human Feedback}}:::interrupt
    DECIDE{Require Revision?}:::decision
    
    %% Second Block: Revision
    subgraph Revision_Workflow [Human-in-the-Loop Revision]
        direction TB
        P5(Phase 5: Research Critique<br/>Supplementary Fact Gathering):::process
        P3_REV(Phase 3: Generation<br/>Revised Final Draft Formed):::process
        
        P5 --> P3_REV
    end

    %% Exit Point
    FINAL([Final Essay Locked]):::final

    %% Connecting Edges
    START --> P1
    P4 --> INTERRUPT
    INTERRUPT --> DECIDE
    
    DECIDE -- "Satisfied (No)" --> FINAL
    DECIDE -- "Revise (Yes)" --> P5
    
    P3_REV --> FINAL

```
- Phase 1: Essay Plan Outline Generated (planner) – Analyzes the prompt and generates a high-level logical structure with specific section-by-section directions.

- Phase 2: Core Research Gathering Complete (research_plan) – Generates target search queries to scrape real-time context and facts via the Tavily API.

- Phase 3: Essay Draft Formed (generate) – Synthesizes the outline plan and researched facts into a coherent 5-paragraph essay draft.

- Phase 4: Teacher's Reflection & Critique (reflect) – Acts as an academic supervisor, analyzing the draft's depth, tone, and stylistic execution, outputting actionable improvement points.

- Phase 5: Supplementary Research via Critique Feedback (research_critique) – If the user approves a revision, this node searches the web again exclusively to patch structural gaps found by the critique before sending the data back to Phase 3 for the final revision output.

## 🛠️ Tech Stack
- Frontend: Streamlit

- Agent Framework: LangGraph & LangChain Core

- LLM Engine: Groq Cloud API (utilizing llama-3.3-70b-versatile)

- Search Engine: Tavily AI

## Web App SS
<img width="1881" height="897" alt="image" src="https://github.com/user-attachments/assets/68bac4d9-ebd5-4af8-9ef4-de79bf58dd14" />

<img width="1534" height="693" alt="image" src="https://github.com/user-attachments/assets/9c7b9a7c-b5ce-45f8-ac6f-7c8b1c1ac315" />

<img width="1881" height="898" alt="image" src="https://github.com/user-attachments/assets/f1b50f99-13d2-48b7-a25a-e04beaa9e23d" />



