import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv 
load_dotenv()    
#load env variables from .env file             


from google.genai import Client
from google.genai.errors import APIError 

# --- Client Initialization ---
# The client automatically looks for the GEMINI_API_KEY environment variable.
try:
    gemini_client = Client()
    print("Gemini Client initialized successfully!")
except Exception as e:
    # A generic catch for environment/API key issues
    print(f"Error initializing Gemini Client: {e}")

api_key = os.getenv("GEMINI_API_KEY") 
client = Client(api_key=GEMINI_API_KEY)

SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def get_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None, "Please set 'SPOTIPY_CLIENT_ID' and 'SPOTIPY_CLIENT_SECRET' in a '.env' file or environment variables"
    
    try:
        #authentication manager
        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            cache_path=f".cache-{client_id}"
        )
        # spotipy client sp
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp, None
    except Exception as e:
        return None, str(e)


def generate_roast(track_genre_data):
    
    if not GEMINI_API_KEY:
        return "FATAL ERROR: GEMINI_API_KEY not set. Cannot generate dynamic roast"

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        return f"GEMINI CLIENT ERROR: Could not initialize client. Check API key. Error: {e}"

    #format the track and genre data for the prompt
    data_string = "\n".join([f"- Track: {t['name']} (Genres: {', '.join(t['genres'])})" for t in track_genre_data])

    prompt = f"""
    Generate a humorous and cutting roast of the user's music taste based on their top Spotify tracks and associated genres. Use witty insults and playful jabs, focusing on the genres and track choices. Please make it funny and also use foul languages in english and hidi as well.Present the roast in a single paragraph.
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