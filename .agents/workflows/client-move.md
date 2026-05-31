Move a prospect to a different pipeline stage.

Usage: /move <prospect_id> <stage>

Valid stages: FOUND, QUALIFIED, LOW_FIT, SKIP, MESSAGED, REPLIED, DEMO_SCHEDULED, BETA_ACTIVE, REVIEW_REQUESTED, PAID

Examples:
- /move abc12345 replied
- /move abc12345 demo_scheduled
- /move abc12345 paid

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && python main.py move $ARGUMENTS
```
