Export prospects to a platform-ready send CSV and open it.

Two export formats available:

**Send CSV** (default — platform import format):
Columns: `email, first_name, custom_subject_1, custom_body_2, custom_body_3, custom_body_4, custom_body_5`
Use this for importing into Instantly, Lemlist, Smartlead, or any cold-email sending platform.

**Enriched CSV** (analysis format):
39 columns including Rufus scores, LinkedIn, all 5 subjects + bodies, weakness signals, stage metadata.
Use this for analysis, reporting, or Apollo bulk import.

---

## Usage

`/export` → send CSV for today's drafted brands
`/export all` → send CSV for all EMAIL_DRAFTED brands (not just today)
`/export enriched` → full 39-column analysis CSV

---

## Step 1 — Run the export

**Send CSV (default):**
```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py export-send
```

**Send CSV all-time:**
```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py export-send --all-time
```

**Enriched CSV:**
```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py export-enriched --stage=EMAIL_DRAFTED
```

---

## Step 2 — Open the file

After the export completes, open the CSV:

```bash
start "" "<filename>"
```

Tell the user the filename and row count from the command output.

---

## Send CSV column reference

| Column | Content | Notes |
|---|---|---|
| `email` | Contact email (verified) | Required for sending |
| `first_name` | Contact first name | Used in greeting |
| `custom_subject_1` | Step 1 subject line | 4–9 words |
| `custom_body_2` | Step 2 follow-up body | Day +3 |
| `custom_body_3` | Step 3 follow-up body | Day +7 |
| `custom_body_4` | Step 4 follow-up body | Day +12 |
| `custom_body_5` | Step 5 break-up body | Day +18 |

Step 1 body is not included — the platform renders it from the sequence template using `custom_subject_1`.
Rows with any empty cell are automatically skipped (brand not fully drafted).
