import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Configure standard output encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import db
    from models import Prospect, Brand
except ImportError:
    # If run outside acquisition_tool path, add to sys.path
    sys.path.append(str(Path(__file__).parent.resolve()))
    import db
    from models import Prospect, Brand

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amazon Rufus AI Optimization Audit — {brand_name}</title>
    <!-- Premium Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    
    <style>
        :root {{
            --bg-dark: #080B11;
            --bg-card: rgba(17, 24, 39, 0.65);
            --bg-glass: rgba(15, 23, 42, 0.45);
            --border-glass: rgba(255, 255, 255, 0.08);
            --text-primary: #F3F4F6;
            --text-secondary: #9CA3AF;
            --text-muted: #6B7280;
            
            /* Status Colors */
            --color-low: #EF4444;
            --color-low-glow: rgba(239, 68, 68, 0.15);
            --color-medium: #F59E0B;
            --color-medium-glow: rgba(245, 158, 11, 0.15);
            --color-high: #10B981;
            --color-high-glow: rgba(16, 185, 129, 0.15);
            
            /* Axis Colors */
            --axis-intent: #FF5E62;
            --axis-attribute: #00F2FE;
            --axis-conversational: #4FACFE;
            --axis-qa: #B92B27;
            --axis-visual: #E100FF;
            --axis-competitive: #11998E;
            
            /* MoMo Gold */
            --color-gold: #D4AF37;
            --color-gold-glow: rgba(212, 175, 55, 0.2);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(17, 56, 122, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(99, 102, 241, 0.1) 0%, transparent 45%);
            background-attachment: fixed;
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        /* Header / Logo bar */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 40px;
            z-index: 100;
            background: linear-gradient(to bottom, rgba(8, 11, 17, 0.8), transparent);
        }}

        .logo-container {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-symbol {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #4FACFE 0%, #00F2FE 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            color: #080B11;
            font-size: 18px;
            box-shadow: 0 0 15px rgba(0, 242, 254, 0.4);
        }}

        .logo-text {{
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #FFFFFF, #9CA3AF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .logo-subtext {{
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
            margin-left: 6px;
            border-left: 1px solid var(--border-glass);
            padding-left: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .credential-badge {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(212, 175, 55, 0.06);
            border: 1px solid rgba(212, 175, 55, 0.25);
            border-radius: 50px;
            font-size: 13px;
            font-weight: 600;
            color: #E5C158;
            box-shadow: 0 0 15px rgba(212, 175, 55, 0.05);
        }}

        .credential-badge svg {{
            fill: #E5C158;
        }}

        /* Slide System */
        .presentation-container {{
            position: relative;
            flex-grow: 1;
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 40px;
        }}

        .slide {{
            position: absolute;
            width: 100%;
            height: 80vh;
            max-height: 720px;
            opacity: 0;
            transform: translateX(100px) scale(0.95);
            transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .slide.active {{
            opacity: 1;
            transform: translateX(0) scale(1);
            pointer-events: auto;
            z-index: 10;
        }}

        .slide.past {{
            opacity: 0;
            transform: translateX(-100px) scale(0.95);
        }}

        .slide-content {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-glass);
            border-radius: 24px;
            height: 100%;
            padding: 48px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow-x: hidden;
            overflow-y: auto;
        }}

        .slide-content::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(to right, #4FACFE, #00F2FE);
        }}

        /* Slide Titles */
        .slide-header {{
            margin-bottom: 24px;
        }}

        .slide-label {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #4FACFE;
            margin-bottom: 8px;
            display: inline-block;
        }}

        .slide-title {{
            font-size: 38px;
            font-weight: 800;
            letter-spacing: -1px;
            color: #FFFFFF;
            line-height: 1.1;
        }}

        .slide-title span {{
            background: linear-gradient(135deg, #FFFFFF 30%, #9CA3AF 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        /* Slide 1: Cover Slide Custom Styles */
        .cover-layout {{
            display: flex;
            height: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 40px;
        }}

        .cover-left {{
            flex: 1.2;
        }}

        .cover-right {{
            flex: 0.8;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-glass);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
        }}

        .cover-pretitle {{
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 3px;
            color: #4FACFE;
            margin-bottom: 16px;
        }}

        .cover-title {{
            font-size: 54px;
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -2px;
            margin-bottom: 24px;
            background: linear-gradient(to right, #FFFFFF, #E5E7EB);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .cover-brand {{
            font-size: 28px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 8px;
            padding: 6px 18px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-glass);
            border-radius: 12px;
            display: inline-block;
        }}

        .cover-meta {{
            font-size: 15px;
            color: var(--text-secondary);
            margin-top: 16px;
            display: flex;
            gap: 20px;
        }}

        .cover-meta span strong {{
            color: #FFFFFF;
        }}

        .rph-seal-large {{
            width: 80px;
            height: 80px;
            background: rgba(212, 175, 55, 0.08);
            border: 2px dashed rgba(212, 175, 55, 0.4);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
            animation: spin-slow 20s linear infinite;
        }}

        .rph-seal-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #E5C158;
            margin-bottom: 8px;
        }}

        .rph-seal-title {{
            font-size: 16px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 12px;
        }}

        .rph-seal-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
        }}

        @keyframes spin-slow {{
            100% {{ transform: rotate(360deg); }}
        }}

        /* Slide 2: The Rufus Era Custom Styles */
        .wedge-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-top: 20px;
            flex-grow: 1;
            align-items: center;
        }}

        .wedge-card {{
            background: rgba(15, 23, 42, 0.45);
            border: 1px solid var(--border-glass);
            border-radius: 16px;
            padding: 32px 24px;
            height: 100%;
            display: flex;
            flex-direction: column;
            transition: transform 0.3s ease, border-color 0.3s ease;
            position: relative;
        }}

        .wedge-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(79, 172, 254, 0.4);
        }}

        .wedge-num {{
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(135deg, #4FACFE 0%, #00F2FE 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 16px;
        }}

        .wedge-title {{
            font-size: 18px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 12px;
        }}

        .wedge-desc {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .wedge-card.highlight {{
            background: rgba(239, 68, 68, 0.04);
            border-color: rgba(239, 68, 68, 0.2);
        }}

        .wedge-card.highlight .wedge-num {{
            background: linear-gradient(135deg, #FF5E62 0%, #FF9966 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        /* Slide 3: Scorecard Custom Styles */
        .scorecard-layout {{
            display: grid;
            grid-template-columns: 0.9fr 1.1fr;
            gap: 40px;
            align-items: center;
            height: 100%;
            margin-top: 20px;
        }}

        .score-circle-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 30px;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-glass);
            border-radius: 20px;
            text-align: center;
        }}

        .score-circle-outer {{
            position: relative;
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }}

        .score-circle-outer::before {{
            content: '';
            position: absolute;
            top: -4px; left: -4px; right: -4px; bottom: -4px;
            border-radius: 50%;
            background: conic-gradient(var(--status-color) {score_percent}%, transparent {score_percent}%);
            z-index: 1;
            filter: drop-shadow(0 0 8px var(--status-color-glow));
        }}

        .score-circle-inner {{
            position: absolute;
            top: 10px; left: 10px; right: 10px; bottom: 10px;
            background: #0B0F19;
            border-radius: 50%;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}

        .score-big-num {{
            font-size: 54px;
            font-weight: 800;
            color: #FFFFFF;
            line-height: 1;
        }}

        .score-max-num {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        .probability-badge {{
            padding: 6px 16px;
            border-radius: 50px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #FFFFFF;
            background: var(--status-color);
            box-shadow: 0 0 15px var(--status-color-glow);
        }}

        .score-summary-text {{
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-top: 16px;
        }}

        .axes-progress-container {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .axis-row {{
            background: rgba(15, 23, 42, 0.25);
            border: 1px solid rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 12px 18px;
        }}

        .axis-row-header {{
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .axis-name {{
            color: #FFFFFF;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .axis-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}

        .axis-value {{
            color: var(--text-secondary);
        }}

        .axis-bar-outer {{
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.08);
            border-radius: 10px;
            overflow: hidden;
        }}

        .axis-bar-inner {{
            height: 100%;
            border-radius: 10px;
            transition: width 1s ease-out;
        }}

        /* Slides 4, 5, 6: Weakness Detail Styles */
        .weakness-layout {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
            margin-top: 16px;
            height: 100%;
        }}

        .weakness-info {{
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            gap: 16px;
            padding-right: 16px;
        }}

        .severity-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            width: fit-content;
        }}

        .severity-badge.critical {{
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #FF5E62;
        }}

        .severity-badge.high {{
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: #F59E0B;
        }}

        .severity-badge.medium {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-glass);
            color: var(--text-secondary);
        }}

        .weakness-desc-box {{
            background: rgba(15, 23, 42, 0.3);
            border: 1px dashed rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .weakness-desc-box strong {{
            color: #FFFFFF;
        }}

        .before-after-container {{
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}

        .code-box {{
            border-radius: 12px;
            overflow: hidden;
            font-size: 13px;
            line-height: 1.5;
            height: 48%;
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border-glass);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}

        .code-box-header {{
            padding: 8px 16px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .code-box.before {{
            background: rgba(15, 23, 42, 0.5);
        }}

        .code-box.before .code-box-header {{
            background: rgba(239, 68, 68, 0.06);
            border-bottom: 1px solid rgba(239, 68, 68, 0.15);
            color: #EF4444;
        }}

        .code-box.after {{
            background: rgba(16, 185, 129, 0.02);
            border-color: rgba(16, 185, 129, 0.25);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.05);
        }}

        .code-box.after .code-box-header {{
            background: rgba(16, 185, 129, 0.08);
            border-bottom: 1px solid rgba(16, 185, 129, 0.2);
            color: #10B981;
        }}

        .code-box-body {{
            padding: 16px;
            font-family: monospace;
            overflow-y: auto;
            flex-grow: 1;
            color: var(--text-secondary);
        }}

        .code-box.after .code-box-body {{
            color: #E6F4EA;
        }}

        /* Slide 7: Roadmap Custom Styles */
        .roadmap-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-top: 16px;
            flex-grow: 1;
            align-items: center;
        }}

        .roadmap-step {{
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-glass);
            border-radius: 16px;
            padding: 24px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
        }}

        .roadmap-step::after {{
            content: '➔';
            position: absolute;
            right: -14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 16px;
            z-index: 5;
        }}

        .roadmap-step:last-child::after {{
            display: none;
        }}

        .roadmap-step-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }}

        .roadmap-step-num {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #4FACFE;
            background: rgba(79, 172, 254, 0.1);
            padding: 4px 10px;
            border-radius: 4px;
        }}

        .roadmap-step-price {{
            font-size: 15px;
            font-weight: 700;
            color: #FFFFFF;
        }}

        .roadmap-step-title {{
            font-size: 16px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 10px;
        }}

        .roadmap-step-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
            flex-grow: 1;
        }}

        .roadmap-step.active-step {{
            border-color: rgba(212, 175, 55, 0.4);
            background: rgba(212, 175, 55, 0.02);
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.05);
        }}

        .roadmap-step.active-step .roadmap-step-num {{
            color: #E5C158;
            background: rgba(212, 175, 55, 0.1);
        }}

        .guarantee-box {{
            background: rgba(16, 185, 129, 0.03);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 12px;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin-top: 16px;
        }}

        .guarantee-icon {{
            font-size: 24px;
            color: #10B981;
        }}

        .guarantee-text {{
            font-size: 13.5px;
            color: var(--text-secondary);
            line-height: 1.4;
        }}

        .guarantee-text strong {{
            color: #FFFFFF;
        }}

        /* Bottom Controls Bar */
        footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px 40px;
            z-index: 100;
            background: linear-gradient(to top, rgba(8, 11, 17, 0.8), transparent);
        }}

        .nav-buttons {{
            display: flex;
            gap: 12px;
        }}

        .nav-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-glass);
            color: #FFFFFF;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            outline: none;
        }}

        .nav-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
            transform: scale(1.05);
        }}

        .nav-btn:active {{
            transform: scale(0.95);
        }}

        .slide-indicator-container {{
            display: flex;
            gap: 8px;
        }}

        .slide-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            cursor: pointer;
            transition: all 0.3s ease;
        }}

        .slide-dot.active {{
            background: #4FACFE;
            width: 24px;
            border-radius: 4px;
        }}

        .page-counter {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-secondary);
            font-variant-numeric: tabular-nums;
        }}

        /* Responsive scaling for standard laptop displays and smaller viewports */
        @media (max-height: 850px) {{
            .slide-content {{
                padding: 24px 32px;
            }}
            .slide-title {{
                font-size: 28px;
            }}
            .slide-header {{
                margin-bottom: 12px;
            }}
            .score-circle-outer {{
                width: 130px;
                height: 130px;
                margin-bottom: 12px;
            }}
            .score-big-num {{
                font-size: 38px;
            }}
            .scorecard-layout {{
                gap: 20px;
                margin-top: 10px;
            }}
            .axis-row {{
                padding: 8px 12px;
            }}
            .axes-progress-container {{
                gap: 10px;
            }}
            .wedge-grid {{
                gap: 16px;
                margin-top: 10px;
            }}
            .wedge-card {{
                padding: 16px;
            }}
            .cover-title {{
                font-size: 38px;
                margin-bottom: 12px;
            }}
            .cover-right {{
                padding: 20px;
            }}
            .roadmap-grid {{
                gap: 12px;
                margin-top: 10px;
            }}
            .roadmap-step {{
                padding: 16px;
            }}
            .guarantee-box {{
                padding: 10px 16px;
                margin-top: 12px;
            }}
            .weakness-layout {{
                gap: 16px;
                margin-top: 8px;
            }}
            .weakness-desc-box {{
                padding: 12px;
                font-size: 13.5px;
            }}
        }}
    </style>
</head>
<body>

    <header>
        <div class="logo-container">
            <div class="logo-symbol">R</div>
            <div class="logo-text">Optimus Rufus</div>
            <div class="logo-subtext">AI Audit</div>
        </div>
        
        <div class="credential-badge">
            <svg width="14" height="14" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/></svg>
            RPh Credential MOAT: Pharmacist-Grade Claim Compliance & PPC Waste Audit
        </div>
    </header>

    <main class="presentation-container">
        <!-- Slide 1: Cover -->
        <div class="slide active" id="slide-1">
            <div class="slide-content">
                <div class="cover-layout">
                    <div class="cover-left">
                        <div class="cover-pretitle">Amazon Rufus AI Optimization Audit</div>
                        <h1 class="cover-title">COSMO Search Engine Moat Teardown</h1>
                        <div style="margin: 32px 0;">
                            <div class="cover-brand">{brand_name}</div>
                        </div>
                        <div class="cover-meta">
                            <span>ASIN: <strong>{anchor_asin}</strong></span>
                            <span>Category: <strong>{category}</strong></span>
                            <span>Date: <strong>{audit_date}</strong></span>
                        </div>
                    </div>
                    <div class="cover-right">
                        <div class="rph-seal-large">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="#E5C158"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                        </div>
                        <div class="rph-seal-label">NexOptimus RPh Advantage</div>
                        <h3 class="rph-seal-title">Pharmacist-CredentialMoat</h3>
                        <p class="rph-seal-desc">Generalist PPC agencies don't understand regulatory compliance. We scan for FDA structure/function compliance to prevent policy-deactivation while slashing high CPC wasteful ad spent.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 2: The Rufus Opportunity -->
        <div class="slide" id="slide-2">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">The Context</span>
                    <h2 class="slide-title">The Massive 2026 <span>Amazon AI Wedge</span></h2>
                </div>
                
                <div class="wedge-grid">
                    <div class="wedge-card">
                        <div class="wedge-num">01</div>
                        <h4 class="wedge-title">The Rufus Search Shift</h4>
                        <p class="wedge-desc">Amazon is systematically shifting keyword-search traffic to <strong>Rufus AI</strong> (powered by COSMO). Rufus answers shopper questions by extracting and citing specific, declarative sentences directly from product listings. No citation = zero organic traffic.</p>
                    </div>
                    
                    <div class="wedge-card highlight">
                        <div class="wedge-num">02</div>
                        <h4 class="wedge-title">Regulatory Crisis Wedges</h4>
                        <p class="wedge-desc">Following the <strong>December 2025 cGMP TIC mandate</strong> and the <strong>March 31, 2026 FDA detail-page claim alignment</strong>, Amazon is programmatically deactivating listings with compliance claim gaps. You need an audit that covers both conversion and regulatory moats.</p>
                    </div>
                    
                    <div class="wedge-card">
                        <div class="wedge-num">03</div>
                        <h4 class="wedge-title">PPC Cannibalization</h4>
                        <p class="wedge-desc">Many supplement/skincare brands waste 30-50% of ad spend running expensive PPC campaigns that cannibalize their own organic rankings or fail to bid on long-tail natural-language terms that Rufus is extracting.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 3: Scorecard -->
        <div class="slide" id="slide-3">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">Performance Dashboard</span>
                    <h2 class="slide-title">COSMO Engine <span>Rufus Scorecard</span></h2>
                </div>
                
                <div class="scorecard-layout">
                    <div class="score-circle-container">
                        <div class="score-circle-outer" style="--status-color: {status_color}; --status-color-glow: {status_color_glow};">
                            <div class="score-circle-inner">
                                <span class="score-big-num">{rufus_score}</span>
                                <span class="score-max-num">/ {max_possible} Max</span>
                            </div>
                        </div>
                        
                        <span class="probability-badge" style="--status-color: {status_color}; --status-color-glow: {status_color_glow};">{rufus_citation_probability} CITATION PROBABILITY</span>
                        <p class="score-summary-text">"{rufus_summary}"</p>
                    </div>
                    
                    <div class="axes-progress-container">
                        <div class="axis-row">
                            <div class="axis-row-header">
                                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-intent);"></span>Intent Alignment</span>
                                <span class="axis-value">{intent_alignment_score} / {axis_max}</span>
                            </div>
                            <div class="axis-bar-outer">
                                <div class="axis-bar-inner" style="width: {intent_alignment_percent}%; background: var(--axis-intent);"></div>
                            </div>
                        </div>
                        
                        <div class="axis-row">
                            <div class="axis-row-header">
                                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-attribute);"></span>Attribute Density</span>
                                <span class="axis-value">{attribute_density_score} / {axis_max}</span>
                            </div>
                            <div class="axis-bar-outer">
                                <div class="axis-bar-inner" style="width: {attribute_density_percent}%; background: var(--axis-attribute);"></div>
                            </div>
                        </div>
                        
                        <div class="axis-row">
                            <div class="axis-row-header">
                                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-conversational);"></span>Conversational Readability</span>
                                <span class="axis-value">{conversational_readability_score} / {axis_max}</span>
                            </div>
                            <div class="axis-bar-outer">
                                <div class="axis-bar-inner" style="width: {conversational_readability_percent}%; background: var(--axis-conversational);"></div>
                            </div>
                        </div>
                        
                        <div class="axis-row">
                            <div class="axis-row-header">
                                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-qa);"></span>Q&A Coverage</span>
                                <span class="axis-value">{qa_coverage_score} / {axis_max}</span>
                            </div>
                            <div class="axis-bar-outer">
                                <div class="axis-bar-inner" style="width: {qa_coverage_percent}%; background: var(--axis-qa);"></div>
                            </div>
                        </div>

                        {v2_axes_block}
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 4: Weakness 1 -->
        <div class="slide" id="slide-4">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">Primary Optimization Gap</span>
                    <h2 class="slide-title">01. {w1_axis_name} <span>Weakness Audit</span></h2>
                </div>
                
                <div class="weakness-layout">
                    <div class="weakness-info">
                        <span class="severity-badge critical">SEVERITY: {w1_severity}</span>
                        <div class="weakness-desc-box">
                            <strong>Observed Issue:</strong><br>
                            {w1_issue}
                        </div>
                        <div style="font-size: 14px; color: var(--text-secondary); line-height: 1.5;">
                            <strong>Why Rufus ignores this:</strong><br>
                            Rufus cannot draw logical conclusions or synthesize missing parameters. If attributes are not explicitly laid out in highly structured, declarative bullets or Q&As, Rufus's semantic weight for this listing drops to zero.
                        </div>
                    </div>
                    
                    <div class="before-after-container">
                        <div class="code-box before">
                            <div class="code-box-header">
                                <span>Current Detail Page Gap</span>
                                <span>✘ NON-COMPLIANT / FLUFF COPY</span>
                            </div>
                            <div class="code-box-body">
                                {w1_before_fluff}
                            </div>
                        </div>
                        
                        <div class="code-box after">
                            <div class="code-box-header">
                                <span>NexOptimus Re-Engineered Bullet & Q&A</span>
                                <span>✔ RUFUS CITED OPTIMIZATION</span>
                            </div>
                            <div class="code-box-body">
                                <strong>Recommended Action:</strong><br>
                                {w1_fix}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 5: Weakness 2 -->
        <div class="slide" id="slide-5">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">Secondary Optimization Gap</span>
                    <h2 class="slide-title">02. {w2_axis_name} <span>Weakness Audit</span></h2>
                </div>
                
                <div class="weakness-layout">
                    <div class="weakness-info">
                        <span class="severity-badge high">SEVERITY: {w2_severity}</span>
                        <div class="weakness-desc-box">
                            <strong>Observed Issue:</strong><br>
                            {w2_issue}
                        </div>
                        <div style="font-size: 14px; color: var(--text-secondary); line-height: 1.5;">
                            <strong>Why it hurts your organic positioning:</strong><br>
                            COSMO context maps seek to match explicit, user-intent filters. When a customer filters by "cruelty-free moisturizer" or "organic dog treat", Amazon's programmatic backfill relies strictly on verified attributes. Vague claims block this matching entirely.
                        </div>
                    </div>
                    
                    <div class="before-after-container">
                        <div class="code-box before">
                            <div class="code-box-header">
                                <span>Current Detail Page Gap</span>
                                <span>✘ MISSING SPECIFICS</span>
                            </div>
                            <div class="code-box-body">
                                {w2_before_fluff}
                            </div>
                        </div>
                        
                        <div class="code-box after">
                            <div class="code-box-header">
                                <span>NexOptimus Re-Engineered Bullet & Q&A</span>
                                <span>✔ RUFUS CITED OPTIMIZATION</span>
                            </div>
                            <div class="code-box-body">
                                <strong>Recommended Action:</strong><br>
                                {w2_fix}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 6: Weakness 3 -->
        <div class="slide" id="slide-6">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">Tertiary Optimization Gap</span>
                    <h2 class="slide-title">03. {w3_axis_name} <span>Weakness Audit</span></h2>
                </div>
                
                <div class="weakness-layout">
                    <div class="weakness-info">
                        <span class="severity-badge medium">SEVERITY: {w3_severity}</span>
                        <div class="weakness-desc-box">
                            <strong>Observed Issue:</strong><br>
                            {w3_issue}
                        </div>
                        <div style="font-size: 14px; color: var(--text-secondary); line-height: 1.5;">
                            <strong>The impact of this optimization:</strong><br>
                            Removing conversational friction and building standalone declarative blocks improves standard customer conversion rate by 15-20% and provides Rufus the precise sentence-lengths optimized for COSMO citations.
                        </div>
                    </div>
                    
                    <div class="before-after-container">
                        <div class="code-box before">
                            <div class="code-box-header">
                                <span>Current Detail Page Gap</span>
                                <span>✘ FLUFF / NO STRUCTURAL METADATA</span>
                            </div>
                            <div class="code-box-body">
                                {w3_before_fluff}
                            </div>
                        </div>
                        
                        <div class="code-box after">
                            <div class="code-box-header">
                                <span>NexOptimus Re-Engineered Bullet & Q&A</span>
                                <span>✔ RUFUS CITED OPTIMIZATION</span>
                            </div>
                            <div class="code-box-body">
                                <strong>Recommended Action:</strong><br>
                                {w3_fix}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide 7: Roadmap -->
        <div class="slide" id="slide-7">
            <div class="slide-content">
                <div class="slide-header">
                    <span class="slide-label">Partnership Roadmap</span>
                    <h2 class="slide-title">The 45-Day <span>Listing Growth Escalator</span></h2>
                </div>
                
                <div class="roadmap-grid">
                    <div class="roadmap-step">
                        <div class="roadmap-step-header">
                            <span class="roadmap-step-num">Step 1</span>
                            <span class="roadmap-step-price">Free</span>
                        </div>
                        <h4 class="roadmap-step-title">Video Teardown</h4>
                        <p class="roadmap-step-desc">A highly personalized, 5-9 minute Loom screencast analyzing listing vulnerabilities and COSMO ranking index gaps (This Video).</p>
                    </div>
                    
                    <div class="roadmap-step active-step">
                        <div class="roadmap-step-header">
                            <span class="roadmap-step-num">Step 2</span>
                            <span class="roadmap-step-price">$297 - $497</span>
                        </div>
                        <h4 class="roadmap-step-title">Founder's Deep Audit</h4>
                        <p class="roadmap-step-desc">A complete 30-point Amazon Detail-Page & FDA claim alignment audit, backed by our pharmacy-moat compliance risk assessment engine.</p>
                    </div>
                    
                    <div class="roadmap-step">
                        <div class="roadmap-step-header">
                            <span class="roadmap-step-num">Step 3</span>
                            <span class="roadmap-step-price">$1.5k - $2.5k</span>
                        </div>
                        <h4 class="roadmap-step-title">30-Day Sprint</h4>
                        <p class="roadmap-step-desc">Hands-on implementation: re-writing 100% of listing copy, backfilling 15+ structured Q&A, and building custom compliant comparison tables.</p>
                    </div>
                    
                    <div class="roadmap-step">
                        <div class="roadmap-step-header">
                            <span class="roadmap-step-num">Step 4</span>
                            <span class="roadmap-step-price">$2k - $3k/mo</span>
                        </div>
                        <h4 class="roadmap-step-title">Growth Retainer</h4>
                        <p class="roadmap-step-desc">Ongoing listing protection, monthly regulatory scans, organic keyword tracking, and fully-managed PPC optimization with waste monitoring.</p>
                    </div>
                </div>
                
                <div class="guarantee-box">
                    <span class="guarantee-icon">🛡</span>
                    <div class="guarantee-text">
                        <strong>Better-than-Money-Back Moat Guarantee:</strong> If after watching the Loom audit or receiving our Deep-Dive audit you don't identify at least <strong>$5,000/month in recoverable ad waste or organic revenue leakage</strong>, we'll refund 100% of the audit cost AND pay you <strong>$100</strong> for your time. No questions asked.
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer>
        <div class="nav-buttons">
            <button class="nav-btn" id="prev-btn" onclick="prevSlide()">◀</button>
            <button class="nav-btn" id="next-btn" onclick="nextSlide()">▶</button>
        </div>
        
        <div class="slide-indicator-container" id="indicators">
            <!-- Programmatic dots -->
        </div>
        
        <div class="page-counter" id="counter">
            1 / 7
        </div>
    </footer>

    <script>
        let currentSlideIndex = 1;
        const totalSlides = 7;
        
        function updateIndicators() {{
            const indicatorsContainer = document.getElementById('indicators');
            indicatorsContainer.innerHTML = '';
            for (let i = 1; i <= totalSlides; i++) {{
                const dot = document.createElement('div');
                dot.className = `slide-dot ${{i === currentSlideIndex ? 'active' : ''}}`;
                dot.onclick = () => showSlide(i);
                indicatorsContainer.appendChild(dot);
            }}
            document.getElementById('counter').innerText = `${{currentSlideIndex}} / ${{totalSlides}}`;
        }}

        function showSlide(index) {{
            if (index < 1 || index > totalSlides) return;
            
            // Update slide classes for smooth sliding transition
            for (let i = 1; i <= totalSlides; i++) {{
                const slide = document.getElementById(`slide-${{i}}`);
                if (i === index) {{
                    slide.className = 'slide active';
                }} else if (i < index) {{
                    slide.className = 'slide past';
                }} else {{
                    slide.className = 'slide';
                }}
            }}
            
            currentSlideIndex = index;
            updateIndicators();
        }}

        function nextSlide() {{
            if (currentSlideIndex < totalSlides) {{
                showSlide(currentSlideIndex + 1);
            }}
        }}

        function prevSlide() {{
            if (currentSlideIndex > 1) {{
                showSlide(currentSlideIndex - 1);
            }}
        }}

        // Keyboard controls
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'Enter') {{
                nextSlide();
            }} else if (event.key === 'ArrowLeft') {{
                prevSlide();
            }}
        }});

        // Initialize indicator dots
        updateIndicators();
    </script>
</body>
</html>
"""

def generate_brand_deck(brand_key: str):
    """Query data for the specified brand_key and output the HTML deck."""
    brand = db.get_brand(brand_key)
    if not brand:
        print(f"Error: Brand '{brand_key}' not found in Supabase database.")
        return False
        
    print(f"Generating presentation for brand: {brand.brand_name} (ASIN: {brand.anchor_asin})...")
    
    # Query anchor prospect
    prospect = db.get_anchor_prospect(brand.anchor_asin)
    if not prospect:
        # Fallback if no anchor prospect linked by ASIN
        print(f"Warning: No anchor prospect found for ASIN '{brand.anchor_asin}' under {brand_key}. Querying by brand_key in prospects...")
        prospects = db.list_prospects()
        matched = [p for p in prospects if p.brand_key == brand_key and p.rufus_score is not None]
        if matched:
            prospect = matched[0]
            print(f"Found matched prospect: {prospect.id} ({prospect.asin})")
        else:
            # Create a mock prospect with default values if none exists
            print("No scored listing found in prospects table. Generating placeholder dashboard details...")
            prospect = Prospect(
                id=brand_key + "_mock",
                username="mock",
                subreddit="mock",
                post_title=brand.brand_name + " listing",
                post_body="Mock bullets",
                post_url="mock",
                asin=brand.anchor_asin,
                brand=brand.brand_name,
                category=brand.category or "Supplements",
                rufus_score=45,
                rufus_citation_probability="low",
                rufus_summary="The listing features generic claims and lacks a conversational Q&A structure, leading to very low citation chances.",
                intent_alignment_score=10,
                attribute_density_score=8,
                conversational_readability_score=12,
                qa_coverage_score=15,
                rufus_top_weaknesses=json.dumps([
                    {
                        "axis": "attribute_density",
                        "issue": "Listing fails to describe structured parameters (such as mg per serving or specific certifications).",
                        "fix": "Rewrite Bullet 1 to state exact dosing parameters clearly.",
                        "severity": "high"
                    },
                    {
                        "axis": "conversational_readability",
                        "issue": "Bullets are written in all-caps marketing pitch style, causing extraction difficulties.",
                        "fix": "Change bullets to declarative lowercase sentences.",
                        "severity": "high"
                    },
                    {
                        "axis": "qa_coverage",
                        "issue": "There are zero answered Q&A pairs on this listing.",
                        "fix": "Seed 10+ standard pre-purchase Q&As regarding dosing and ingredients.",
                        "severity": "medium"
                    }
                ])
            )

    # Format values for HTML template
    score = prospect.rufus_score or 45
    
    # Check if this is a V2 score (6-axis, max 120) or V1 (4-axis, max 100)
    is_v2 = False
    max_possible = 100
    axis_max = 25
    if prospect.visual_structured_content_score is not None or prospect.competitive_relativity_score is not None:
        is_v2 = True
        max_possible = 120
        axis_max = 20

    score_percent = int((score / max_possible) * 100)
    
    prob = (prospect.rufus_citation_probability or "low").upper()
    status_color = "var(--color-low)"
    status_color_glow = "var(--color-low-glow)"
    if prob == "MEDIUM":
        status_color = "var(--color-medium)"
        status_color_glow = "var(--color-medium-glow)"
    elif prob == "HIGH":
        status_color = "var(--color-high)"
        status_color_glow = "var(--color-high-glow)"
        
    # Axis scores percentages
    def get_percent(val):
        return int((val or 0) / axis_max * 100)
        
    intent_percent = get_percent(prospect.intent_alignment_score)
    attr_percent = get_percent(prospect.attribute_density_score)
    conv_percent = get_percent(prospect.conversational_readability_score)
    qa_percent = get_percent(prospect.qa_coverage_score)
    
    v2_axes_block = ""
    if is_v2:
        vis_percent = get_percent(prospect.visual_structured_content_score)
        comp_percent = get_percent(prospect.competitive_relativity_score)
        v2_axes_block = f"""
        <div class="axis-row">
            <div class="axis-row-header">
                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-visual);"></span>Visual & Structured Content</span>
                <span class="axis-value">{prospect.visual_structured_content_score} / 20</span>
            </div>
            <div class="axis-bar-outer">
                <div class="axis-bar-inner" style="width: {vis_percent}%; background: var(--axis-visual);"></div>
            </div>
        </div>
        
        <div class="axis-row">
            <div class="axis-row-header">
                <span class="axis-name"><span class="axis-dot" style="background: var(--axis-competitive);"></span>Competitive Relativity</span>
                <span class="axis-value">{prospect.competitive_relativity_score} / 20</span>
            </div>
            <div class="axis-bar-outer">
                <div class="axis-bar-inner" style="width: {comp_percent}%; background: var(--axis-competitive);"></div>
            </div>
        </div>
        """

    # Parse weaknesses
    weaknesses = []
    if prospect.rufus_top_weaknesses:
        try:
            weaknesses = json.loads(prospect.rufus_top_weaknesses)
        except Exception:
            pass
            
    # Pad to 3 weaknesses
    while len(weaknesses) < 3:
        weaknesses.append({
            "axis": "general",
            "issue": "Listing lacks structural formatting optimized for natural language parsing.",
            "fix": "Break large blocks of text into small, readable statements.",
            "severity": "medium"
        })
        
    def clean_axis_name(name):
        return name.replace("_", " ").title()

    # Before-fluff placeholders to simulate side-by-side comparison
    before_fluffs = {
        "intent_alignment": "Title: 'Premium Wellness Formula - Super Food Complex' (Shoppers never type this. They search: 'Organic Greens Powder for Bloating Relief').",
        "attribute_density": "Bullets: 'Made with natural ingredients that are premium sourced.' (No mention of USDA Organic certification or serving size in count).",
        "conversational_readability": "Bullets: '★ BEST SELLING FORMULA ★ AMAZING OUTCOMES FOR ALL AGES!!!' (All caps, superlatives, emoji spam which Rufus ignores).",
        "qa_coverage": "Q&A Section: 'No Q&A pairs exist. Customers must browse reviews to find serving size, allergen information, or origin details.'",
        "visual_structured_content": "Images: 'Only 3 product shots on plain white background. No infographic, no comparison chart, and A+ content is disabled.'",
        "competitive_relativity": "Benchmark: 'Trailing top 3 competitors on 4 distinct citation channels. Competitor A has 18 Q&As vs your 0.'"
    }

    w1 = weaknesses[0]
    w1_axis = w1.get("axis", "intent_alignment")
    w1_before = before_fluffs.get(w1_axis, "Standard generic listing text without structure.")
    
    w2 = weaknesses[1]
    w2_axis = w2.get("axis", "attribute_density")
    w2_before = before_fluffs.get(w2_axis, "Missing specific quantities or third-party test details.")
    
    w3 = weaknesses[2]
    w3_axis = w3.get("axis", "conversational_readability")
    w3_before = before_fluffs.get(w3_axis, "Bullets are heavily nested and contain sales pitches.")

    html = HTML_TEMPLATE.format(
        brand_name=brand.brand_name,
        anchor_asin=brand.anchor_asin,
        category=brand.category or "Health & Wellness",
        audit_date=datetime.now().strftime("%B %d, %Y"),
        rufus_score=score,
        max_possible=max_possible,
        score_percent=score_percent,
        rufus_citation_probability=prob,
        status_color=status_color,
        status_color_glow=status_color_glow,
        rufus_summary=prospect.rufus_summary or "The listing fails to optimize for conversational search queries.",
        axis_max=axis_max,
        intent_alignment_score=prospect.intent_alignment_score or 0,
        intent_alignment_percent=intent_percent,
        attribute_density_score=prospect.attribute_density_score or 0,
        attribute_density_percent=attr_percent,
        conversational_readability_score=prospect.conversational_readability_score or 0,
        conversational_readability_percent=conv_percent,
        qa_coverage_score=prospect.qa_coverage_score or 0,
        qa_coverage_percent=qa_percent,
        v2_axes_block=v2_axes_block,
        
        # Weakness 1
        w1_axis_name=clean_axis_name(w1_axis),
        w1_severity=w1.get("severity", "high").upper(),
        w1_issue=w1.get("issue", ""),
        w1_fix=w1.get("fix", ""),
        w1_before_fluff=w1_before,
        
        # Weakness 2
        w2_axis_name=clean_axis_name(w2_axis),
        w2_severity=w2.get("severity", "high").upper(),
        w2_issue=w2.get("issue", ""),
        w2_fix=w2.get("fix", ""),
        w2_before_fluff=w2_before,
        
        # Weakness 3
        w3_axis_name=clean_axis_name(w3_axis),
        w3_severity=w3.get("severity", "medium").upper(),
        w3_issue=w3.get("issue", ""),
        w3_fix=w3.get("fix", ""),
        w3_before_fluff=w3_before
    )
    
    # Save the output file
    presentations_dir = Path("presentations")
    presentations_dir.mkdir(exist_ok=True)
    
    output_file = presentations_dir / f"{brand_key}_teardown.html"
    output_file.write_text(html, encoding="utf-8")
    
    print(f"Success! Beautiful HTML presentation generated at: {output_file.resolve()}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python generate_presentation.py <brand_key>    - Generates a slide deck for one brand")
        print("  python generate_presentation.py all            - Generates slide decks for all draft-stage brands")
        print("\nAvailable draft-stage brands to audit:")
        try:
            db.init_db()
            drafts = db.get_brands_by_stage("EMAIL_DRAFTED", limit=20)
            if not drafts:
                print("  No brands currently in EMAIL_DRAFTED stage.")
            for d in drafts:
                print(f"  - {d.brand_key} (Brand: {d.brand_name}, ASIN: {d.anchor_asin})")
        except Exception as e:
            print(f"  Error loading brands: {e}")
        return

    db.init_db()
    arg = sys.argv[1]
    
    if arg == "all":
        drafts = db.get_brands_by_stage("EMAIL_DRAFTED", limit=100)
        if not drafts:
            print("No brands in EMAIL_DRAFTED stage to generate decks for.")
            return
        
        count = 0
        for d in drafts:
            if generate_brand_deck(d.brand_key):
                count += 1
        print(f"\nDone! Generated {count} presentation decks in the 'presentations/' directory.")
    else:
        generate_brand_deck(arg)

if __name__ == "__main__":
    main()
