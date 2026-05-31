#!/usr/bin/env python3
import sys
import os
import argparse
import datetime

def generate_header(topic: str, framework_name: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""# Brainstorming Session: {framework_name}
**Topic:** {topic}
**Date/Time:** {timestamp}
---

"""

def run_scamper(topic: str) -> str:
    output = generate_header(topic, "SCAMPER Framework")
    output += f"""> [!TIP]
> Use the SCAMPER framework to systematically iterate on the target concept (**{topic}**).

| Letter | Principle | Guided Brainstorming Prompts for "{topic}" |
| :---: | :--- | :--- |
| **S** | **Substitute** | What components, libraries, or steps in the flow of {topic} can we replace to increase value or speed? |
| **C** | **Combine** | How can we merge {topic} with another existing feature or product to create a unique hybrid value proposition? |
| **A** | **Adapt** | How can we adapt {topic} so it appeals to a completely different user segment (e.g., Enterprise users, non-technical buyers)? |
| **M** | **Modify / Magnify** | What happens if we magnify the key selling point or styling of {topic}? Can we make a specific element larger or faster? |
| **P** | **Put to another use** | How could {topic} be utilized in a completely different context or category? |
| **E** | **Eliminate** | What is the single most complicated or redundant element of {topic} that we can completely remove to simplify the user experience? |
| **R** | **Reverse / Rearrange** | What if we reverse the sequence of events or layout of {topic}? What if the end goal becomes the starting point? |

### 📝 SCAMPER Notes & Action Items
*   **Substitute Idea:** __________________
*   **Combine Idea:** __________________
*   **Adapt Idea:** __________________
*   **Modify Idea:** __________________
*   **Put to another use Idea:** __________________
*   **Eliminate Idea:** __________________
*   **Reverse Idea:** __________________
"""
    return output

def run_hats(topic: str) -> str:
    output = generate_header(topic, "Six Thinking Hats Evaluation")
    output += f"""> [!IMPORTANT]
> The Six Thinking Hats framework organizes parallel thinking, separating facts from emotions and risks from creative leaps.

### ⚪ White Hat (Facts & Data)
*   What raw facts, data, API limitations, or performance metrics do we know about **{topic}**?
*   *Notes:* __________________

### 🔴 Red Hat (Feelings & Intuition)
*   What is our immediate gut reaction or emotional feeling about **{topic}**? How will users feel when they interact with it?
*   *Notes:* __________________

### ⚫ Black Hat (Caution & Risk)
*   What could go wrong? What are the security, performance, cost, or compliance risks associated with **{topic}**?
*   *Notes:* __________________

### 🟡 Yellow Hat (Benefits & Optimism)
*   What is the best possible outcome? What are the key values, cost savings, or conversion improvements of **{topic}**?
*   *Notes:* __________________

### 🟢 Green Hat (Creativity & Alternatives)
*   What are the wildest, most out-of-the-box variations or complementary additions we can make to **{topic}**?
*   *Notes:* __________________

### 🔵 Blue Hat (Process & Strategy)
*   How do we organize the next steps? What is our checklist for implementing **{topic}**?
*   *Notes:* __________________
"""
    return output

def run_cosmo(topic: str) -> str:
    output = generate_header(topic, "Amazon COSMO Semantic Expansion")
    output += f"""> [!NOTE]
> The Amazon COSMO & Rufus optimization framework expands the semantic surface area of the listing to match natural consumer questions.

```mermaid
graph TD
    Topic["{topic}"] --> Intent["1. Conversational Intent Paths"]
    Topic --> Context["2. Usage Context & Settings"]
    Topic --> Associations["3. Semantic Vector Matches"]
```

### 1. Conversational Buyer Intent Paths
Brainstorm the exact questions customers ask Google or Rufus before realizing they need **{topic}**:
*   *Question A:* "What is the best way to solve [pain point solved by {topic}]?"
*   *Question B:* "Is there a sustainable/premium alternative for [common alternative to {topic}]?"
*   *Question C:* "How can I improve my daily routine when dealing with [target context]?"

### 2. Usage Contexts & Lifestyle Scenarios
Where and when is **{topic}** used? Let's brainstorm the explicit settings to seed in our COSMO graph mapping:
*   *Setting/Location:* e.g., office desk, gym bag, morning ritual, kitchen drawer.
*   *Target Demographic Lifestyles:* e.g., eco-conscious parents, productivity enthusiasts, active outdoor adventurers.

### 3. Semantic Vector Association Targets
What complementary product terms or synonyms have high semantic overlap with **{topic}** in embedding space?
*   *Synonyms:* __________________
*   *Complementary Products:* __________________
*   *Adjacent Categories:* __________________

### 🎯 Optimized Seed Recommendations
Draft 3 custom Q&A pairs combining these axes:
1.  **Q:** __________________ \n**A:** __________________
2.  **Q:** __________________ \n**A:** __________________
3.  **Q:** __________________ \n**A:** __________________
"""
    return output

def main():
    # Force UTF-8 stdout/stderr encoding for terminals (especially Windows)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Optimus Rufus Brainstorming & Ideation CLI Helper")
    subparsers = parser.add_subparsers(dest="command", help="The brainstorming framework to run")

    # SCAMPER parser
    scamper_parser = subparsers.add_parser("scamper", help="Run a SCAMPER ideation session")
    scamper_parser.add_argument("--topic", required=True, type=str, help="The concept, feature, or product to brainstorm")
    scamper_parser.add_argument("--export", action="store_true", help="Export the report to the reports/ folder")

    # Hats parser
    hats_parser = subparsers.add_parser("hats", help="Run a Six Thinking Hats session")
    hats_parser.add_argument("--topic", required=True, type=str, help="The design proposal or idea to evaluate")
    hats_parser.add_argument("--export", action="store_true", help="Export the report to the reports/ folder")

    # COSMO expansion parser
    cosmo_parser = subparsers.add_parser("cosmo-expansion", help="Run an Amazon COSMO listing semantic expansion session")
    cosmo_parser.add_argument("--topic", required=True, type=str, help="The Amazon product or keyword category")
    cosmo_parser.add_argument("--export", action="store_true", help="Export the report to the reports/ folder")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Execute selected framework
    if args.command == "scamper":
        result = run_scamper(args.topic)
    elif args.command == "hats":
        result = run_hats(args.topic)
    elif args.command == "cosmo-expansion":
        result = run_cosmo(args.topic)
    else:
        result = ""

    # Print results
    print(result)

    # Export if requested
    if args.export:
        os.makedirs("reports", exist_ok=True)
        filename = f"reports/brainstorming_session_{args.command}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"\n[SUCCESS] Brainstorming report successfully exported to: {os.path.abspath(filename)}")

if __name__ == "__main__":
    main()
