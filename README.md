# Music Roast (Streamlit + Spotify)

Quick Streamlit app that fetches your top Spotify tracks and shows audio features.

Setup
1. Create a `.env` file in the project root with these keys:

```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
# Optional: SPOTIPY_REDIRECT_URI (defaults to http://127.0.0.1:8888/callback)
```

2. Install dependencies (prefer a virtualenv):

```bash
pip install -r requirements.txt
```

Run

```bash
streamlit run main.py
```

Notes
- The app uses Spotipy's OAuth flow and will open a browser to authenticate.
- OAuth tokens are cached locally in a `.cache-*` file created by Spotipy.
- The app currently displays audio features; roast generation is a placeholder you can extend.
