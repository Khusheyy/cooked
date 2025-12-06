import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

#load env variables from .env file
load_dotenv()

SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def get_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None, "Please set `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` in a `.env` file or environment variables."
    
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



st.set_page_config(page_title="Music Roast", page_icon="🎵")
st.title("🎵 Music Roast Generator")
st.write("Get ready to laugh at your own music taste! Click the button below to fetch your top Spotify tracks.")


if st.button("Fetch my top tracks"):
    with st.spinner("Authenticating with Spotify and fetching data..."):
        sp, err = get_spotify_client()

    if err:
        st.error(err)
    else:
        try:
            # fetch the user's top 10 tracks
            top_tracks = sp.current_user_top_tracks(limit=10, time_range='short_term')
            items = top_tracks.get('items', [])
            
            if not items:
                st.info("No top tracks available for your account (or you need to play more music).")
            else:
                track_data = []
                # returns tracks in order(rank)
                for i, track in enumerate(items):
                    # Ranking Score is just a numerical value (10 down to 1) for chart plotting
                    rank_score = 10 - i 
                    track_data.append({
                        'Rank': 10 - rank_score + 1, # Convert back to display rank (1 to 10)
                        'Track Name': track['name'],
                        'Artist(s)': ', '.join(artist['name'] for artist in track['artists']),
                        'Album': track['album']['name'],
                        'Ranking Score': rank_score
                    })

                df_tracks = pd.DataFrame(track_data)
                
                # Create a DataFrame optimized for charting (Track Name + Artist as index, Ranking Score as value)
                df_chart = df_tracks.copy()
                # Create a combined label for better chart display
                df_chart['Track & Artist'] = df_chart.apply(
                    lambda row: f"{row['Rank']}. {row['Track Name']} by {row['Artist(s)']}", axis=1
                )
                df_chart.set_index('Track & Artist', inplace=True)

                ## 📊 Your Top Tracks Chart
                st.subheader("📊 Your Top Tracks by Rank")
                st.write("This bar chart visualizes your top 10 tracks, ordered by rank (1 = highest).")
                
                # Display the chart element using the Ranking Score as the numerical value
                st.bar_chart(df_chart['Ranking Score'], height=400)
                
                ## 📝 Top Tracks Details
                st.subheader("📝 Top Tracks Details")
                # Display the raw track list in a table
                st.dataframe(df_tracks[['Rank', 'Track Name', 'Artist(s)', 'Album']], use_container_width=True, hide_index=True)

                # --- Roast Generation Placeholder ---
                # Collect all unique artists from the top tracks for the "roast" input
                all_artists = set()
                for track in items:
                    for artist in track['artists']:
                        all_artists.add(artist['name'])
                
                artist_list = sorted(list(all_artists))
                st.markdown(f"**Artists for Roast:** {', '.join(artist_list)}")
                
                st.markdown("**Next:** Use the list of artists above to generate a critique or 'roast' of your music taste.")


        except spotipy.SpotifyException as se:
            # Handle Spotify API errors
            st.error(f"Spotify API error: HTTP {getattr(se, 'http_status', 'N/A')} - {getattr(se, 'msg', str(se))}")
            st.info("Common fixes: delete the local Spotipy cache file ('.cache-*'), ensure your `.env` redirect URI matches the app settings, then re-authenticate.")
        except Exception as e:
            st.exception(e)

else:
    st.info("Click the button above to authenticate with Spotify and fetch your top tracks.")