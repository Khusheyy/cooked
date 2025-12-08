import os
import uuid
import glob
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# ---- Gemini API ----
from google import genai
from google.genai import types
from google.genai.errors import APIError 

# Load environment variables
load_dotenv()

# ---- CONFIG ----
SCOPE = "user-top-read"
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------
#  SPOTIFY AUTH SETUP
# ---------------------------------------------------------------
def get_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

    if not client_id or not client_secret:
        return None, "Missing Spotify credentials in your .env file!"

    # A unique session-based cache
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    cache_path = f".cache-{client_id}-{st.session_state.session_id}"

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=cache_path,
        show_dialog=True,
    )

    token_info = auth_manager.get_cached_token()

    if token_info:
        return spotipy.Spotify(auth_manager=auth_manager), None

    return None, auth_manager.get_authorize_url()


# ---------------------------------------------------------------
#  GEMINI ROAST GENERATOR
# ---------------------------------------------------------------
def generate_roast(track_list):
    if not track_list:
        return "I can’t roast you—there are no tracks here. Spotify thinks you're a musical ghost."

    prompt = f"""
You are a humorous roasting AI. Create a **funny, playful, non-offensive roast** 
about the user's music taste using the tracks below.

Tracks:
{track_list}

Rules:
- Be witty and sarcastic.
- No slurs or abusive content.
- Keep it 3–5 sentences max.
"""

    try:
        result = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return result.text.strip()

    except RequestError as e:
        return f"(Gemini API Error) {e}"

    except Exception:
        return "My roast generator crashed… kind of like your playlists."


# ---------------------------------------------------------------
#  FETCH & RENDER TRACKS
# ---------------------------------------------------------------
def render_tracks(sp):
    top = sp.current_user_top_tracks(limit=10, time_range="short_term")
    items = top.get("items", [])

    if not items:
        st.warning("You need to listen to more music before I can roast you!")
        return

    rows = []
    track_strings = ""

    for i, track in enumerate(items, start=1):
        name = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])
        rows.append([i, name, artists])
        track_strings += f"{i}. {name} by {artists}\n"

    df = pd.DataFrame(rows, columns=["Rank", "Track", "Artist"])

    # Show table
    st.subheader("🎵 Your Top Spotify Tracks")
    st.dataframe(df, hide_index=True, use_container_width=True)

    # Gemini roast
    st.subheader("🔥 AI Roast of Your Music Taste")
    roast = generate_roast(track_strings)
    st.markdown(f"> {roast}")


# ---------------------------------------------------------------
#  CLEAR SPOTIFY TOKENS
# ---------------------------------------------------------------
def clear_cache():
    cid = os.getenv("SPOTIPY_CLIENT_ID")
    if not cid:
        return

    for path in glob.glob(f".cache-{cid}-*"):
        os.remove(path)

    st.session_state.clear()
    st.success("Spotify cache cleared. Refresh page to re-login.")


# ---------------------------------------------------------------
#  MAIN APP
# ---------------------------------------------------------------
def main():
    st.set_page_config(page_title="Music Taste Roaster", page_icon="🔥")

    st.title("🔥 Spotify Music Taste Roaster (AI Powered)")

    with st.sidebar:
        if st.button("Clear Spotify Login Cache"):
            clear_cache()

    sp, auth_url = get_spotify_client()

    if sp:
        render_tracks(sp)
        return

    # No token → redirect user
    st.info("Click below to log in to Spotify:")
    st.markdown(f"[**Login with Spotify**]({auth_url})")
    components.html(
        f"<script>window.location.href='{auth_url}';</script>",
        height=0
    )


if __name__ == "__main__":
    main()
