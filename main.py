import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv


# confg the credentials
def configure():
    load_dotenv()
  
configure()

# 1. Setup - Replace with your actual credentials
SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback" 

# 2. Authenticate the user (This opens a browser window)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope=SCOPE,
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=SPOTIPY_REDIRECT_URI
))

# 3. Get the user's top 10 tracks (adjustable 'limit' and 'time_range')
top_tracks_results = sp.current_user_top_tracks(limit=10, time_range='medium_term')

# 4. Process the data into a clean, text-friendly format
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
# print(data_string)


# from google import genai
# from google.genai import types

# # --- 1. Initialize Gemini Client ---
# # The client will automatically use the GEMINI_API_KEY environment variable.
# try:
#     client = genai.Client()
# except Exception as e:
#     print(f"Error initializing Gemini Client. Ensure GEMINI_API_KEY is set: {e}")
#     exit()

# # --- 2. Define the Persona (The Critic) ---
# # System Instructions are key for setting the tone and role.
# SYSTEM_PROMPT = (
#   "You are 'The Cooked Critic,' a vicious, over-educated music snob whose degree in 'Musicology of the Mundane' is utterly worthless. You are a total bastard. Your sole purpose is to unleash a brutal, hilarious, and profanity-laced roast of the user's music taste (based on the provided tracks/genres). Use music terminology incorrectly and contemptuously for maximum comedic effect. Question every goddamn life choice they have ever made. You are a judgmental, foul-mouthed cunt of a critic. DO NOT be nice. DO NOT hold back. Format the response using professional, scathing headings and bolding."
# )

# # --- 3. Construct the User Prompt ---
# USER_PROMPT = (
#     f"Roast this user's music taste. This is their top 15 tracks from the last six months. "
#     f"Use the genre data to find embarrassing contradictions or cliches.\n\n"
#     f"--- USER'S TOP MUSIC ---\n{data_string}\n--- END LIST ---"
# )

# # --- 4. Call the Gemini API ---
# try:
#     response = client.models.generate_content(
#         model='gemini-2.5-flash',
#         contents=USER_PROMPT,
#         config=types.GenerateContentConfig(
#             system_instruction=SYSTEM_PROMPT,
#             temperature=0.9,  # High temperature for more creative, funny output
#         )
#     )
    
#     print("\n" + "="*50)
#     print("      💀 THE ROAST HAS BEEN SERVED 💀")
#     print("="*50)
#     print(response.text)
#     print("="*50 + "\n")

# except Exception as e:
#     print(f"Failed to generate roast: {e}")