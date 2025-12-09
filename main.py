import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import uuid
import glob
import pandas as pd
import os
from dotenv import load_dotenv

# --- Configuration & Initialization ---

load_dotenv()

# Load API keys and config
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
# MUST be an HTTPS URL matching one registered in your Spotify App Settings
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "https://cooked.streamlit.app/callback")
SCOPE = "user-top-read"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Gemini Client Initialization (Simplified) ---

# The client automatically looks for the GEMINI_API_KEY environment variable.
# We keep this block simple and let the function handle the error if the key is missing.
gemini_client = None
try:
    gemini_client = Client(api_key=GEMINI_API_KEY)
    # The print statement is removed for cleaner Streamlit deployment logs, but 
    # you can keep it for local testing if you prefer.
    # print("Gemini Client initialized successfully!") 
except Exception as e:
    # Handle the case where the key is missing/invalid
    print(f"Error initializing Gemini Client: {e}") 
    from google.genai import Client # Import here if not already imported globally
    from google.genai.errors import APIError

# --- Core Authentication Function (Fixed) ---

def get_spotify_client():
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
        return None, "Please set 'SPOTIPY_CLIENT_ID' and 'SPOTIPY_CLIENT_SECRET' in a '.env' file or environment variables"

    # Ensure each Streamlit session gets a unique cache (avoids token reuse across users)
    if 'sp_session_id' not in st.session_state:
        st.session_state['sp_session_id'] = str(uuid.uuid4())

    # Spotipy cache path
    cache_path = f".cache-{SPOTIPY_CLIENT_ID}-{st.session_state['sp_session_id']}"

    try:
        # Authentication manager using the fixed HTTPS redirect URI
        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            cache_path=cache_path,
            show_dialog=True
        )

        # 1. Try to get a token from the cache first (e.g., if already authorized)
        token_info = auth_manager.get_cached_token()

        if token_info and token_info.get('access_token'):
            access_token = token_info['access_token']
            sp = spotipy.Spotify(auth=access_token)
            return sp, None

        # 2. If no valid token in cache, check query parameters for an OAuth code
        query_params = st.query_params
        # Streamlit standardizes query params to lists; we want the first item
        code_list = query_params.get('code')
        code = code_list[0] if code_list else None

        if code:
            # Exchange code for token
            try:
                # Use code to get the token, which also saves it to the cache file
                token_info = auth_manager.get_access_token(code=code, as_dict=True)
                access_token = token_info.get('access_token')
                if not access_token:
                    raise Exception('No access token returned after code exchange')
                
                # Clear the 'code' from query parameters to prevent re-exchange on rerun
                # Note: st.query_params.clear() is available in newer Streamlit versions
                # For compatibility, we can rely on Streamlit's refresh after auth.
                # However, for robustness, we return the client and let the app proceed.
                sp = spotipy.Spotify(auth=access_token)
                return sp, None
            except Exception as ex:
                # This is where your original 'invalid_grant' error occurred
                return None, f"Failed to exchange code for token: {ex}. **Ensure the 'SPOTIPY_REDIRECT_URI' in your .env file EXACTLY matches the Redirect URI registered in your Spotify App Dashboard.**"

        # 3. If no token and no code, generate authorization URL for the user to click
        auth_url = auth_manager.get_authorize_url()
        
        st.write("### 🔑 Spotify Authorization Required")
        st.write(f"Click the link below to authorize the app. Spotify will redirect you back to **{SPOTIPY_REDIRECT_URI}** with the authorization code.")
        st.markdown(f"[Authorize App and Get My Music Roast!]({auth_url})")
        return None, "User authorization required: follow the authorize link shown above."

    except Exception as e:
        return None, str(e)

# --- Roast Generation Function (Cleaned) ---

def generate_roast(track_genre_data):
    if not GEMINI_API_KEY:
        return "FATAL ERROR: GEMINI_API_KEY not set. Cannot generate dynamic roast"

    if gemini_client is None:
         return "GEMINI CLIENT ERROR: Could not initialize client. Check API key."

    # format the track and genre data for the prompt
    data_string = "\n".join([f"- Track: {t['name']} (Genres: {', '.join(t['genres'])})" for t in track_genre_data])

    prompt = f"""
    Generate a humorous and cutting roast of the user's music taste based on their top Spotify tracks and associated genres. Use witty insults and playful jabs, focusing on the genres and track choices. Please make it funny and also use foul languages in english and hidi as well.Present the roast in a single paragraph.
    ---
    {data_string}
    ---
    """
    
    try:
        # Call the Gemini API
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except APIError as e:
        return f"GEMINI API ERROR: The API call failed. Check your API key and permissions. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred during roast generation: {e}"


# --- Streamlit App Code (Unchanged logic, just using cleaned functions) ---

st.set_page_config(page_title="Music Roast", page_icon="🎵")
st.title("🎵 Music Roast Generator 🎵")
st.write("Get ready to laugh at your own music taste! Click the button below to fetch your top Spotify tracks.")

# Allow users to clear the Spotify cache and force re-authentication
client_id_preview = SPOTIPY_CLIENT_ID # Use the constant defined earlier


def clear_spotify_cache(client_id_preview: str) -> int:
    """Remove any local Spotipy cache files for the current client id and reset session id.

    Returns the number of files removed.
    """
    if not client_id_preview:
        return 0
    # Note: Streamlit Cloud does not have a persistent local filesystem for the cache
    # to be truly effective. This is primarily useful for local development.
    pattern = f".cache-{client_id_preview}-*"
    removed = 0
    for f in glob.glob(pattern):
        try:
            os.remove(f)
            removed += 1
        except Exception:
            pass
    # reset session id so a new cache file will be created on next auth
    st.session_state.pop('sp_session_id', None)
    return removed


if client_id_preview:
    # Backend-only: automatically clear Spotipy cache once per Streamlit session
    already_cleared_for = st.session_state.get('sp_cache_cleared_for_client')
    if already_cleared_for != client_id_preview:
        removed = clear_spotify_cache(client_id_preview)
        st.session_state['sp_cache_cleared_for_client'] = client_id_preview
        if removed:
            print(f"Cleared {removed} Spotipy cache file(s) for client {client_id_preview}.")
        # else:
            # print(f"No Spotipy cache files found for client {client_id_preview}.")


if st.button(" Reveal my musical sins "):
    with st.spinner("Authenticating with Spotify, fetching data, and preparing the critique..."):
        # This call will handle authorization, either through cache, code, or URL redirect
        sp, err = get_spotify_client()

    if err:
        # Display the error/authorization message returned by get_spotify_client
        st.error(err)
    else:
        try:
            # ... (rest of the Spotify data fetching and processing logic remains here)
            # fetch the user's top 10 tracks
            top_tracks = sp.current_user_top_tracks(limit=10, time_range='short_term')
            items = top_tracks.get('items', [])
            
            track_genre_data = [] 
            
            if not items:
                st.info("No top tracks available for your account (or you need to play more music).")
            else:
                # collect Data and Artists for Genre Lookup
                track_data_temp = []
                artist_ids = []
                
                for track in items:
                    track_data_temp.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': ', '.join(artist['name'] for artist in track['artists']),
                        'album': track['album']['name'],
                        'artist_ids': [artist['id'] for artist in track['artists']],
                        'genres': [] # Placeholder
                    })
                    artist_ids.extend([artist['id'] for artist in track['artists']])
                
                # fetch Genres for all Unique Artists
                unique_artist_ids = list(set(artist_ids))
                artist_details = {}
                
                if unique_artist_ids:
                    for i in range(0, len(unique_artist_ids), 50):
                        chunk = unique_artist_ids[i:i + 50]
                        details = sp.artists(chunk)
                        for artist in details['artists']:
                            artist_details[artist['id']] = artist.get('genres', [])

                # populate Track Data with Genres and Prepare Chart Data
                df_rows = []
                
                for i, track in enumerate(track_data_temp):
                    all_genres = set()
                    for artist_id in track['artist_ids']:
                        all_genres.update(artist_details.get(artist_id, []))
                    
                    track['genres'] = list(all_genres)
                    
                    # prepare data for chart/table display
                    rank_score = 10 - i 
                    df_row = {
                        'Rank': i, 
                        'Track Name': track['name'],
                        'Artist(s)': track['artists'],
                        'Album': track['album'],
                        'Genres': ', '.join(track['genres']) if track['genres'] else 'N/A',
                        'Ranking Score': rank_score
                    }
                    
                    track_genre_data.append(track) # for roast generation
                    df_rows.append(df_row)

                df_tracks = pd.DataFrame(df_rows)
                
                # Create chart DataFrame
                df_chart = df_tracks.copy()
                df_chart['Track & Artist'] = df_chart.apply(
                    lambda row: f"{row['Rank']}. {row['Track Name']} by {row['Artist(s)']}", axis=1
                )
                df_chart.set_index('Track & Artist', inplace=True)
                
                
                # --- Streamlit Display ---
                
                ## top tracks chart
                st.subheader("📊 Your Top Tracks by Rank")
                st.write("Visualized by rank (1 = top track).")
                st.bar_chart(df_chart['Ranking Score'], height=400)
                
                ## track details (including genres)
                st.subheader("📝 Track Details (Including Genres)")
                st.dataframe(df_tracks[['Rank', 'Track Name', 'Artist(s)', 'Album', 'Genres']], width='stretch', hide_index=True)

            # --- The Dynamic Roast Section ---
            st.markdown("---")
            st.header("🔥 The Music Roast 🔥")
            
            roast = generate_roast(track_genre_data)
            
            # Display the Roast
            st.error(f"**WARNING: CRITICAL TASTE FAILURE DETECTED**")
            st.markdown(f"> **Final Verdict:** {roast}")
            st.markdown("---")

        except spotipy.SpotifyException as se:
            st.error(f"Spotify API error: HTTP {getattr(se, 'http_status', 'N/A')} - {getattr(se, 'msg', str(se))}")
            st.info("Common fixes: delete the local Spotipy cache file ('.cache-*'), ensure your `.env` redirect URI matches the app settings, then re-authenticate.")
        except Exception as e:
            st.exception(e)

else:
    st.info("Click the button above to authenticate with Spotify and fetch your top tracks.")