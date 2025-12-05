import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv


# confg the credentials
def configure():
    load_dotenv()
  
configure()


SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback" 

# auth w spotify
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope=SCOPE,
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=SPOTIPY_REDIRECT_URI
))


top_tracks_results = sp.current_user_top_tracks(limit=10, time_range='medium_term')

listening_data = []
for i, track in enumerate(top_tracks_results['items']):
    artist_name = track['artists'][0]['name']
    track_name = track['name']
    
    # Optional: Get artist genre for a deeper roast (requires another call)
    artist_info = sp.artist(track['artists'][0]['id'])
    genres = ", ".join(artist_info.get('genres', ['Unknown Genre']))
    
    listening_data.append(f"{i+1}. Song: '{track_name}' by Artist: {artist_name} (Genres: {genres})")

# Final data string to send to Gemini
data_string = "\n".join(listening_data)
print(data_string)

st.set_page_config(page_title="Music Roast", page_icon="🎵")
st.title("🎵 Music Roast Generator")
st.write("Get ready to laugh at your own music taste! Click the button below to generate a hilarious roast based on your top Spotify tracks.")
