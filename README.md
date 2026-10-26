# Minutes of Meeting

A simple Streamlit app that turns a meeting into clear, organized minutes using the Gemini API.

## Features

- Upload your meeting and get minutes generated automatically
- Clean summary of what was discussed
- Key decisions and action items in one place
- Simple web interface, no setup headaches

## Tech Stack

- Python
- Streamlit
- Google Gemini API

## Project Structure

```
meeting-app/
├── app.py            # Streamlit interface
├── core.py           # Main logic (Gemini calls, processing)
├── requirements.txt  # Python dependencies
└── .streamlit/
    └── config.toml   # Streamlit settings
```

## Getting Started

### 1. Clone the repo

```
git clone https://github.com/Zoohiiie/Minutes-of-Meeting.git
cd Minutes-of-Meeting
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Add your API key

Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/), then create a file at `.streamlit/secrets.toml`:

```
GEMINI_API_KEY = "your-api-key-here"
```

This file is ignored by git, so your key stays private. Never upload it to GitHub.

### 4. Run the app

```
streamlit run app.py
```

It opens in your browser at `http://localhost:8501`.

## Deploying

You can host it for free on [Streamlit Community Cloud](https://streamlit.io/cloud). Connect this repo, then add `GEMINI_API_KEY` under the app's **Secrets** settings instead of using `secrets.toml`.

## Author

Made by [Zoohiiie](https://github.com/Zoohiiie)
