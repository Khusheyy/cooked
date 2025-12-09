import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import uuid
import glob
import pandas as pd
import os
import socket
from urllib.parse import urlparse, urlunparse, parse_qs
from dotenv import load_dotenv 
load_dotenv()    
#load env variables from .env file             


from google.genai import Client
from google.genai.errors import APIError 

#
# client automatically looks for the GEMINI_API_KEY environment variable
try:
    gemini_client = Client()
    print("Gemini Client initialized successfully!")
except Exception as e:
    # A generic catch for environment/API key issues
    print(f"Error initializing Gemini Client: {e}")
# Load Gemini API key from environment early so it's available for initialization
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# The client will use the explicit API key if provided, otherwise it falls back
# to the client's automatic environment lookup behavior.
try:
    if GEMINI_API_KEY:
        gemini_client = Client(api_key=GEMINI_API_KEY)
    else:
        gemini_client = Client()
    print("Gemini Client initialized successfully!")
except Exception as e:
    # A generic catch for environment/API key issues
    print(f"Error initializing Gemini Client: {e}")

SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "https://cooked.streamlit.app/callback")


def get_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None, "Please set 'SPOTIPY_CLIENT_ID' and 'SPOTIPY_CLIENT_SECRET' in a '.env' file or environment variables"
    
    try:
        # Ensure each Streamlit session gets a unique cache to avoid reusing
        # a developer's previously-authorized token. This forces each user
        # to authenticate with their own Spotify account.
        if 'sp_session_id' not in st.session_state:
            st.session_state['sp_session_id'] = str(uuid.uuid4())

        cache_path = f".cache-{client_id}-{st.session_state['sp_session_id']}"

        # Determine a safe redirect URI: try the configured one first, but if the
        # port is already bound, pick an available ephemeral port to avoid
        # "Address already in use" errors when Spotipy starts a local server.
        configured_redirect = os.getenv("SPOTIPY_REDIRECT_URI", SPOTIPY_REDIRECT_URI)
        parsed = urlparse(configured_redirect)
        host = parsed.hostname or '127.0.0.1'
        path = parsed.path or '/callback'
        scheme = parsed.scheme or 'http'

        # Decide whether the redirect host is a loopback. If it's not (for
        # example a deployed domain like cooked.streamlit.app) we MUST NOT try
        # to bind a local socket to that host — attempting to do so raises
        # "Cannot assign requested address" or similar errors. In those cases
        # we'll skip the local-server flow and use the manual paste-back flow.
        port = parsed.port
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        def _is_port_free(h, p):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((h, p))
                s.close()
                return True
            except OSError:
                return False

        if not is_loopback:
            # Non-localhost redirect (deployed). Do not attempt to bind — go
            # straight to using the configured redirect and the manual flow.
            redirect_to_use = configured_redirect
            print(f"Redirect host '{host}' is not loopback — skipping local-server OAuth flow.")
        else:
            # Try using the configured port; if it's busy, choose an ephemeral port.
            if port is None or not _is_port_free(host, port):
                # pick an ephemeral free port on localhost
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind((host, 0))
                port = s.getsockname()[1]
                s.close()
                # store chosen redirect in session so subsequent reruns reuse it
                st.session_state['sp_chosen_redirect'] = f"{scheme}://{host}:{port}{path}"
                redirect_to_use = st.session_state['sp_chosen_redirect']
                print(f"Configured redirect port was busy — using ephemeral port {port} for OAuth callback.")
            else:
                redirect_to_use = configured_redirect

        # authentication manager
        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_to_use,
            cache_path=cache_path,
            show_dialog=True
        )

        # Try to obtain a token. In some deployment environments the local
        # HTTP server used by Spotipy cannot bind (or the redirect URI is not
        # registered). Attempt the usual flow first and fall back to a manual
        # authorize URL + paste-back redirect flow if that fails.
        try:
            # Prefer a cached token if available (avoids starting local server).
            token_info = auth_manager.get_cached_token()
            if token_info:
                access_token = token_info.get('access_token') if isinstance(token_info, dict) else token_info
                if access_token:
                    sp = spotipy.Spotify(auth=access_token)
                    return sp, None

            # If the redirect host is loopback, we can attempt the interactive
            # local-server flow; otherwise skip straight to manual fallback.
            if is_loopback:
                token_result = auth_manager.get_access_token()
                if isinstance(token_result, dict):
                    access_token = token_result.get('access_token')
                else:
                    access_token = token_result

                if not access_token:
                    raise Exception("No token returned from auth manager")

                sp = spotipy.Spotify(auth=access_token)
                return sp, None
            # else: fall through to manual fallback
        except OSError as ose:
            # Likely "Address already in use" when starting local server.
            print(f"Local server OAuth failed: {ose}; falling back to manual flow.")
        except Exception:
            # Other failures will also try manual fallback below.
            pass

        # Manual fallback for deployed environments (Streamlit Cloud).
        # If Spotify redirects back to this app URL, the code will appear in
        # the query params — pick it up automatically and exchange it. If no
        # code is present, show the authorize URL so the user can sign in.
        try:
            auth_url = auth_manager.get_authorize_url()
            # First check whether Spotify already redirected back with a code
            # (this happens on deployed apps if the redirect URI is the app URL).
            query_params = st.experimental_get_query_params()
            code_list = query_params.get('code') or query_params.get('CODE')
            code = code_list[0] if code_list else None

            if code:
                # Exchange code for token
                try:
                    token_info = auth_manager.get_access_token(code=code)
                    access_token = token_info['access_token'] if isinstance(token_info, dict) else token_info
                    sp = spotipy.Spotify(auth=access_token)
                    return sp, None
                except Exception as ex:
                    return None, f"Failed to exchange code for token: {ex}"

            # No code present yet: show authorize link and instruct the user to
            # click it and complete authorization. Spotify will redirect back
            # to this app with the code, and the app will pick it up on reload.
            st.write("### Spotify authorization required")
            st.write("Click the link below to authorize the app. After authorizing, Spotify will redirect you back to this page and the app will continue automatically.")
            st.markdown(f"[Authorize here]({auth_url})")
            return None, "User authorization required: follow the authorize link shown above."
        except Exception as e:
            return None, f"OAuth fallback failed: {e}"
        # spotipy client sp
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp, None
    except Exception as e:
        return None, str(e)


def generate_roast(track_genre_data):
    
    if not GEMINI_API_KEY:
        return "FATAL ERROR: GEMINI_API_KEY not set. Cannot generate dynamic roast"

    try:
        # Prefer the already-initialized global client when available
        client = gemini_client if 'gemini_client' in globals() else Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        return f"GEMINI CLIENT ERROR: Could not initialize client. Check API key. Error: {e}"

    #format the track and genre data for the prompt
    data_string = "\n".join([f"- Track: {t['name']} (Genres: {', '.join(t['genres'])})" for t in track_genre_data])

    prompt = f"""
    Generate a humorous and cutting roast of the user's music taste based on their top Spotify tracks and associated genres. Use witty insults and playful jabs, focusing on the genres and track choices. Please make it funny and also use foul languages in english and hindi as well.Present the roast in a single paragraph.
    ---
    {data_string}
    ---
    """
    
    try:
        # Call the Gemini API
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except APIError as e:
        return f"GEMINI API ERROR: The API call failed. Check your API key and permissions. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred during roast generation: {e}"


# streamlit app codee

st.set_page_config(page_title="Music Roast", page_icon="🎵")
st.title("🎵 Music Roast Generator 🎵")
st.write("Get ready to laugh at your own music taste! Click the button below to fetch your top Spotify tracks.")

# Allow users to clear the Spotify cache and force re-authentication
client_id_preview = os.getenv("SPOTIPY_CLIENT_ID")


def clear_spotify_cache(client_id_preview: str) -> int:
    
    if not client_id_preview:
        return 0
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
    # for the current client id. This avoids any UI controls (checkboxes/buttons).
    # We store the client id for which we've already cleared in session state so
    # we don't repeatedly delete cache files on every rerun.
    already_cleared_for = st.session_state.get('sp_cache_cleared_for_client')
    if already_cleared_for != client_id_preview:
        removed = clear_spotify_cache(client_id_preview)
        # mark as cleared for this client id
        st.session_state['sp_cache_cleared_for_client'] = client_id_preview
        # No Streamlit UI feedback (backend-only). Print to logs for debugging.
        if removed:
            print(f"Cleared {removed} Spotipy cache file(s) for client {client_id_preview}.")
        else:
            print(f"No Spotipy cache files found for client {client_id_preview}.")


if st.button(" Reveal my musical sins "):
    with st.spinner("Authenticating with Spotify, fetching data, and preparing the critique..."):
        sp, err = get_spotify_client()

    if err:
        st.error(err)
    else:
        try:
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
                st.dataframe(df_tracks[['Rank', 'Track Name', 'Artist(s)', 'Album', 'Genres']], use_container_width=True, hide_index=True)

            # --- The Dynamic Roast Section ---
            # Now track_genre_data is guaranteed to be defined (either empty or populated)
            st.markdown("---")
            st.header("🔥 The Music Roast 🔥")
            
            # Generate the roast using the Gemini API
            # This call is outside the `else` block to be near the display logic, 
            # but relies on track_genre_data being initialized earlier.
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