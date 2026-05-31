---
name: brainstorming
description: "Brainstorming and ideation skill manual for generating new ideas, naming products, developing features, drafting campaigns, and structured problem-solving. Triggers: brainstorm, ideation, name ideas, creative brainstorming, generate ideas, feature brainstorming."
metadata:
  author: Antigravity Agent
  version: "1.0.0"
---

# Creative Brainstorming & Ideation Skill

This skill manual details the frameworks, heuristics, and operational runbook for conducting high-fidelity **creative brainstorming and ideation** within the **Optimus Rufus** ecosystem.

Whether developing new product positioning, mapping out feature enhancements for the dashboard, designing growth marketing hooks, or debugging tricky system bottlenecks, this skill provides structured cognitive models to break through creative plateaus.

---

## 1. Core Brainstorming Frameworks

Use the most suitable framework below depending on the nature of the brainstorming request:

### A. SCAMPER (Feature & Product Adaptation)
Best for taking an existing product, listing, or software component and finding creative iterations:
*   **S**ubstitute: What components, materials, or API libraries can we swap out?
*   **C**ombine: Can we merge this feature with another to create a unique hook?
*   **A**dapt: How can we adjust this solution to fit a completely different user segment?
*   **M**odify/Magnify: What happens if we emphasize a particular feature, size, or styling?
*   **P**ut to another use: How can this tool solve a completely different problem?
*   **E**liminate: What is redundant, bloated, or overly complex? Let's strip it back.
*   **R**everse/Rearrange: What if we invert the user flow or run the pipeline backwards?

### B. Six Thinking Hats (Structured Evaluation)
Best for collaborative validation and evaluating a proposed design from multiple perspectives:
*   ⚪ **White Hat (Facts)**: What raw data, performance benchmarks, or user conversion numbers do we have?
*   🔴 **Red Hat (Feelings)**: What is our gut reaction, or the immediate emotional appeal to the customer?
*   ⚫ **Black Hat (Caution)**: What could go wrong? What are the edge cases, risks, and compliance hurdles?
*   🟡 **Yellow Hat (Optimism)**: What is the best-case scenario? What are the high-value opportunities?
*   🟢 **Green Hat (Creativity)**: What are alternative, out-of-the-box, or slightly crazy ideas?
*   🔵 **Blue Hat (Process)**: How should we structure our next steps? What is our action plan?

### C. First Principles (Architectural Debugging & Innovation)
Best for complex engineering bottlenecks or re-architecting systems from scratch:
1.  **Deconstruct**: Identify and list all current assumptions (e.g., *"We must use a third-party scraper"*).
2.  **Isolate Fundamentals**: Reduce the problem to its immutable, fundamental physical/logical truths (e.g., *"We just need HTML elements matching standard product selectors"*).
3.  **Reconstruct**: Build up a new, elegant solution from these fundamental truths.

### D. Amazon COSMO Semantic Expansion (Listing Growth)
Specifically tuned for **Amazon Rufus search optimization**. When brainstorming how to increase listing visibility, expand along these semantic axes:
*   **User Intent Paths**: What conversational questions does a customer ask before finding our product category?
*   **Usage Contexts**: Where, when, and with whom is this product used? (e.g., "energy drink for late-night gaming sessions").
*   **Semantic Association Mapping**: What complementary products, lifestyles, or pain points share high similarity in the embedding vector space?

---

## 2. Interactive CLI Helper (Runbook)

A dedicated Python wizard is available to guide interactive sessions or generate pre-formatted templates.

### A. Run an Interactive SCAMPER Session
Step through each letter of the SCAMPER acronym interactively to brainstorm product enhancements:
```powershell
python .agents/skills/brainstorming/scripts/brainstorm.py scamper --topic "Dashboard ROI Calculator"
```

### B. Generate a Six Thinking Hats Matrix
Assess a feature design, system change, or business idea through the Six Hats lens:
```powershell
python .agents/skills/brainstorming/scripts/brainstorm.py hats --topic "Migrating to Supabase serverless cache"
```

### C. Run COSMO Semantic Keyword Expansion
Brainstorm semantic questions and contextual links for Amazon Rufus discovery:
```powershell
python .agents/skills/brainstorming/scripts/brainstorm.py cosmo-expansion --topic "Eco-friendly bamboo toothbrush"
```

---

## 3. Formatting & Presenting Results

When delivering brainstorming outputs to the user, ensure **visual excellence** and **clear structure**:

1.  **Use Dynamic Layouts**: Incorporate markdown callout blocks (`[!TIP]`, `[!IMPORTANT]`) and beautiful tables to keep information scannable.
2.  **Avoid Placeholders**: Present real, concrete ideas that the user can immediately act upon.
3.  **Include a Clear Action Plan**: Conclude every brainstorming session with a **Blue Hat Process Checklist** or next-step roadmap.
