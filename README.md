# 📚 Coursera Transcript Generator

A beautiful CLI tool to bulk-download transcripts and subtitles from any Coursera course you're enrolled in.

![CLI Preview](https://raw.githubusercontent.com/KavinMK05/coursera-transcript-generator/master/preview.png)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-brightgreen)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/coursera-transcripts?period=total&units=NONE&left_color=BLACK&right_color=RED&left_text=downloads)](https://pepy.tech/projects/coursera-transcripts)

---

## ✨ Features

- **Interactive prompts** — guided step-by-step experience, no need to memorize flags
- **Bulk download** — grabs every lecture transcript in a course at once
- **Organized output** — files are sorted by module and lesson, in course order
- **Metadata manifests** — every run produces JSON and CSV download reports
- **Progress tracking** — real-time progress bar with download status
- **Retry logic** — automatic retries with exponential backoff on failures
- **Multiple formats** — supports both `.txt` (plain text) and `.srt` (subtitle) formats
- **Multi-language** — download transcripts in any available language

---

## 📦 Installation

```bash
# Clone the repo
git clone https://github.com/your-username/coursera-transcript-generator.git
cd coursera-transcript-generator

# Install in editable mode
pip install -e .
```

---

## 🚀 Usage

### Interactive Mode (recommended)

Just run the command with no arguments — it will guide you through everything:

```bash
coursera-transcripts
```

You'll be prompted for:

1. **CAUTH cookie** — your Coursera authentication token
2. **Course slug** — the identifier from the course URL
3. **Options** — language, format, and output directory

### CLI Mode

Pass everything as flags for scripting / automation:

```bash
export COURSERA_CAUTH="YOUR_CAUTH_VALUE"
coursera-transcripts \
  --slug "machine-learning" \
  --language en \
  --format txt \
  --output ./transcripts
```

### All Options

| Flag         | Short | Default      | Description                    |
| ------------ | ----- | ------------ | ------------------------------ |
| `--cookie`   | `-c`  | env/prompt   | CAUTH cookie value             |
| `--slug`     | `-s`  | _(prompted)_ | Course slug from URL           |
| `--language` | `-l`  | `en`         | Subtitle language code         |
| `--format`   |       | `txt`        | Output format (`txt` or `srt`) |
| `--output`   | `-o`  | `./output`   | Parent output directory        |

---

## 🔑 Getting Your CAUTH Cookie

1. Open [coursera.org](https://www.coursera.org) and **log in**
2. Open **DevTools** (`F12` or `Ctrl+Shift+I`)
3. Go to **Application** → **Cookies** → `https://www.coursera.org`
4. Find the cookie named **`CAUTH`**
5. Copy its **Value**

> [!IMPORTANT]
> You must be **enrolled** in the course to download its transcripts.

The interactive cookie prompt hides its input. For automation, prefer the
`COURSERA_CAUTH` environment variable over `--cookie`, which may expose the
value in shell history or process listings.

---

## 📁 Output Structure

Transcripts are organized by module and lesson. Numeric prefixes preserve the
course order, and the language is included in each filename:

```
output/
└── machine-learning/
    ├── manifest.json
    ├── manifest.csv
    ├── manifest.en.txt.json
    ├── manifest.en.txt.csv
    ├── 01-Introduction to Machine Learning/
    │   └── 01-Getting Started/
    │       ├── 001-Welcome to Machine Learning--abc123.en.txt
    │       └── 002-What is Machine Learning--def456.en.txt
    └── 02-Linear Regression/
        └── 01-Models and Cost/
            ├── 001-Model Representation--ghi789.en.txt
            └── 002-Cost Function--jkl012.en.txt
```

Transcript files contain the subtitle text returned by Coursera, unchanged.
`manifest.json` and `manifest.csv` record course/module/lesson/video names, IDs,
slugs and positions, plus language, duration, optional/locked flags, output
path, download status, and any error for every lecture.

The unqualified manifests describe the latest run. Language/format-specific
manifests preserve each output set independently. On a completed repeat run,
files recorded by the prior matching manifest but no longer belong at their
old paths are moved into a timestamped `.stale/` archive. A failed refresh
preserves the last successful file and records it as `previous_path`.
Interrupted runs retain partial files and write an interrupted manifest
without performing stale-file reconciliation.

---

## 🔧 Finding the Course Slug

The slug is the part of the URL after `/learn/`:

```
https://www.coursera.org/learn/machine-learning
                                └── this is the slug
```

---

## 📋 Requirements

- Python **3.10+**
- A Coursera account with enrollment in the target course

---

## 📄 License

MIT
