---
name: frontend-launcher
description: "Use when starting or auditing the development servers (Vite calculator, Next.js dashboard, FastAPI backend) and instantly launching the user's web browser for checking. Triggers: launch frontend, open browser, start local check, show in browser, launch calculator."
metadata:
  author: Antigravity Agent
  version: "1.0.0"
---

# Frontend Browser Launcher Skill

This skill governs the automated startup, port auditing, and visual checking of frontend interfaces within the **Optimus Rufus** workspace. 

It provides the AI agent with standard, reliable methods to start background development servers and trigger the user's default system browser for instant checking.

---

## 1. Quick Trigger Commands

The dedicated Python launcher script handles background process management and web browser redirection seamlessly.

### A. Launch the React/Vite Pricing Calculator (Port 5173)
Checks if port 5173 is open. If closed, starts the dev server in the background and opens the default browser:
```powershell
backend-venv\Scripts\python.exe .agents/skills/frontend-launcher/scripts/launch.py --service calc
```

### B. Launch the Next.js Admin Dashboard (Port 3000)
Checks if port 3000 is open, starts Next.js development server if closed, and triggers the browser:
```powershell
backend-venv\Scripts\python.exe .agents/skills/frontend-launcher/scripts/launch.py --service dashboard
```

### C. Launch the FastAPI Backend API (Port 8000)
Starts the FastAPI backend and opens the browser directly to the interactive swagger docs (`/docs`):
```powershell
backend-venv\Scripts\python.exe .agents/skills/frontend-launcher/scripts/launch.py --service backend
```

---

## 2. Dynamic Port Auditing Heuristics

The underlying Python script audits service ports using standard TCP socket binding routines:
1.  **Check Bindability**: Attempts to open a brief socket connection to `localhost` on the target port.
2.  **State Assessment**:
    *   **Port Open**: The service is already running. The launcher bypasses startup to prevent process conflicts and immediately triggers `webbrowser.open()`.
    *   **Port Closed**: The service is inactive. The launcher spins up a detached background subprocess (e.g. `npm run dev`) before opening the browser.

---

## 3. Custom Profiles & Deep Linking

To check a specific ASIN audit profile or submission directly:
```powershell
# Open a specific pre-calculated profile ID in the browser
backend-venv\Scripts\python.exe .agents/skills/frontend-launcher/scripts/launch.py --service calc --path "/profile/sample-uuid-id"
```
This is extremely useful during email prospecting verification, letting you audit the visual layout of any client profile instantly.
