import os
import uuid

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from dotenv import load_dotenv

# --- Configuration & Initialization ---
load_dotenv()

# Gemini (Google) client
from google.genai import Client
from google.genai.errors import APIError

# Load Gemini API key (if available) and initialize client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    # Client will automatically pick up GEMINI_API_KEY from env if set
    gemini_client = Client()
    # print("Gemini Client initialized successfully!") # Don't print to Streamlit app stdout
except Exception as e:
    gemini_client = None
    # print(f"Error initializing Gemini Client: {e}") # Don't print to Streamlit app stdout

# Spotify / Streamlit constants
SCOPE = "user-top-read"
# Default to a common development URI, but honor the .env setting
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def get_spotify_client():
    """Return (sp, None) when authenticated, or (None, auth_url) when not authenticated, or (None, error_string) on error."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

    if not client_id or not client_secret:
        return None, "Please set 'SPOTIPY_CLIENT_ID' and 'SPOTIPY_CLIENT_SECRET' in a '.env' file or environment variables"

    try:
        # Use a per-session cache file so each site visitor authenticates separately
        if 'sp_session_id' not in st.session_state:
            st.session_state['sp_session_id'] = str(uuid.uuid4())
        # Cache file name uses client_id and session_id for uniqueness
        cache_path = f".cache-{client_id}-{st.session_state['sp_session_id']}"

        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            cache_path=cache_path,
            show_dialog=True,
        )

        # SpotifyOAuth stores tokens in the cache file after redirect/callback.
        try:
            token_info = auth_manager.get_cached_token()
        except Exception:
            token_info = None

        if token_info:
            sp = spotipy.Spotify(auth_manager=auth_manager)
            return sp, None
        else:
            # Not authenticated, return the authorization URL
            auth_url = auth_manager.get_authorize_url()
            return None, auth_url
    except Exception as e:
        return None, str(e)


def generate_roast(track_genre_data):
    """Generate a roast using the Gemini API based on track and genre data."""
    if not gemini_client:
        return "FATAL ERROR: Gemini client not initialized. Cannot generate roast."

    # format the track and genre data for the prompt
    data_string = "\n".join([f"- Track: {t['name']} (Genres: {', '.join(t.get('genres', []))})" for t in track_genre_data])

    prompt = f"""
Generate a humorous and cutting roast of the user's music taste based on their top Spotify tracks and associated genres. 
Use witty insults and playful jabs, focusing on the genres and track choices. Keep it funny and avoid abusive slurs.
---
{data_string}
---
"""

    try:
        response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except APIError as e:
        return f"GEMINI API ERROR: {e}"
    except Exception as e:
        return f"An unexpected error occurred during roast generation: {e}"


def render_tracks_and_roast(sp):
    """Fetches user data, displays tracks, and generates the roast."""
    try:
        # fetch the user's top 10 tracks
        top_tracks = sp.current_user_top_tracks(limit=10, time_range='short_term')
        items = top_tracks.get('items', [])

        track_genre_data = []

        if not items:
            st.info("No top tracks available for your account (or you need to play more music).")
            return

        # 1. Collect Data and Artists for Genre Lookup
        track_data_temp = []
        artist_ids = []

        for track in items:
            track_data_temp.append({
                'id': track['id'],
                'name': track['name'],
                'artists': ', '.join(artist['name'] for artist in track['artists']),
                'album': track['album']['name'],
                'artist_ids': [artist['id'] for artist in track['artists']],
                'genres': []
            })
            artist_ids.extend([artist['id'] for artist in track['artists']])

        # 2. Fetch Genres from unique artists
        unique_artist_ids = list(set(artist_ids))
        artist_details = {}

        if unique_artist_ids:
            # Batch API calls to fetch artist details (Spotify limit is 50 per request)
            for i in range(0, len(unique_artist_ids), 50):
                chunk = unique_artist_ids[i:i + 50]
                details = sp.artists(chunk)
                for artist in details['artists']:
                    if artist: # check for None in case an ID was invalid
                        artist_details[artist['id']] = artist.get('genres', [])

        # 3. Populate Track Data with Genres and Prepare Display Data
        df_rows = []
        for i, track in enumerate(track_data_temp):
            all_genres = set()
            for artist_id in track['artist_ids']:
                all_genres.update(artist_details.get(artist_id, []))

            track['genres'] = list(all_genres)

            rank_score = 10 - i
            df_row = {
                'Rank': i + 1, # Use 1-based indexing for display
                'Track Name': track['name'],
                'Artist(s)': track['artists'],
                'Album': track['album'],
                'Genres': ', '.join(track['genres']) if track['genres'] else 'N/A',
                'Ranking Score': rank_score
            }

            track_genre_data.append(track)
            df_rows.append(df_row)

        df_tracks = pd.DataFrame(df_rows)
        df_chart = df_tracks.copy()
        df_chart['Track & Artist'] = df_chart.apply(
            lambda row: f"{row['Rank']}. {row['Track Name']} by {row['Artist(s)']}", axis=1
        )
        df_chart.set_index('Track & Artist', inplace=True)

        # --- Streamlit Display ---
        st.subheader("📊 Your Top Tracks by Rank")
        st.write("Visualized by rank (1 = top track).")
        st.bar_chart(df_chart['Ranking Score'], height=400)

        st.subheader("📝 Track Details (Including Genres)")
        st.dataframe(df_tracks[['Rank', 'Track Name', 'Artist(s)', 'Album', 'Genres']], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.header("🔥 The Music Roast 🔥")
        roast = generate_roast(track_genre_data)
        st.error("**WARNING: CRITICAL TASTE FAILURE DETECTED**")
        st.markdown(f"> **Final Verdict:** {roast}")
        st.markdown("---")

    except spotipy.SpotifyException as se:
        st.error(f"Spotify API error: {se}")
        st.info("Please ensure your `.env` settings are correct and try refreshing to re-authenticate.")
    except Exception as e:
        st.exception(e)


def main():
    """Main Streamlit application function."""
    st.set_page_config(page_title="Music Roast", page_icon="🎵")
    st.title("🎵 Music Roast Generator 🎵")
    st.write("Get ready to laugh at your own music taste! Requires Spotify & Gemini API keys.")

    # Get Spotify client, or auth URL/error message
    sp, auth_or_err = get_spotify_client()

    if sp:
        # Authenticated, proceed to render content
        render_tracks_and_roast(sp)
        return

    # Not authenticated, check if it's an auth URL or an error
    if isinstance(auth_or_err, str) and auth_or_err.startswith("http"):
        # This is the authentication URL
        st.info("Redirecting to Spotify for authentication...")
        # Attempt automatic redirect; if popup blocked, show link
        components.html(f"<script>window.location.href = '{auth_or_err}';</script>")
        st.markdown(f"[Click here to authenticate with Spotify]({auth_or_err})")
        st.stop()
    elif auth_or_err:
        # This is an error message
        st.error(auth_or_err)
    else:
        # Should not happen, but as a fallback
        st.error("Unknown authentication state. Try refreshing the page.")


if __name__ == '__main__':
    main()