import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from streamlit_agraph import agraph, Node, Edge, Config

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SCOPE = "user-top-read"
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def get_spotify_client():
    """
    Initializes and returns a Spotipy client object and an error message (if any).
    """
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None, "Please set `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` in a `.env` file or environment variables."
    
    try:
        # Authentication manager
        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            cache_path=f".cache-{client_id}"
        )
        # Spotipy client
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp, None
    except Exception as e:
        return None, str(e)


# --- Streamlit Application ---

st.set_page_config(page_title="Music Roast Graph", page_icon="🎵")
st.title("🎵 Music Roast Network Generator")
st.write("Click the button below to fetch your top Spotify tracks and visualize the connections between the artists.")

st.markdown("**Privacy note:** OAuth tokens are cached locally in a `.cache-*` file created by Spotipy.")

if st.button("Fetch my top tracks and build graph"):
    with st.spinner("Authenticating with Spotify and fetching data..."):
        sp, err = get_spotify_client()

    if err:
        st.error(err)
    else:
        try:
            # Fetch the user's top 10 tracks
            top_tracks = sp.current_user_top_tracks(limit=10, time_range='short_term')
            items = top_tracks.get('items', [])
            
            if not items:
                st.info("No top tracks available for your account (or you need to play more music).")
                
            else:
                # --- Graph Data Generation ---
                nodes = []
                edges = []
                all_artist_ids = set()
                
                # 1. Create Nodes (Artists)
                for track in items:
                    for artist in track['artists']:
                        if artist['id'] not in all_artist_ids:
                            all_artist_ids.add(artist['id'])
                            nodes.append(Node(
                                id=artist['id'],
                                label=artist['name'],
                                size=20,
                                color="#1DB954", # Spotify Green
                                title=f"Artist: {artist['name']}",
                            ))
                
                # 2. Create Edges (Tracks connecting Artists)
                for track in items:
                    artist_ids = [artist['id'] for artist in track['artists']]
                    
                    # If multiple artists on a track, connect them
                    if len(artist_ids) > 1:
                        # Create edges between all pairs of artists on the track
                        for i in range(len(artist_ids)):
                            for j in range(i + 1, len(artist_ids)):
                                # Use a composite ID for the edge to ensure uniqueness per track/artist pair
                                edge_id = f"{artist_ids[i]}-{artist_ids[j]}-{track['id']}"
                                
                                edges.append(Edge(
                                    source=artist_ids[i],
                                    target=artist_ids[j],
                                    label=track['name'],
                                    title=f"Track: {track['name']}",
                                    color="#FFFFFF", # White for edges
                                    width=1
                                ))
                    
                    # If only one artist, we can connect them to a 'Self-Node' or just display the node.
                    # For simplicity, we'll focus on collaborative edges.

                
                ## 🌐 Interactive Artist Network Graph
                st.subheader("🌐 Your Top Tracks Artist Network")
                st.write("This interactive graph shows the **Artists** (nodes) and the **Tracks** (edges) that connect them, highlighting collaborations in your top 10.")
                
                # --- Configure Graph ---
                config = Config(
                    width=700,
                    height=500,
                    directed=False,
                    physics=True,
                    # Configure the nodes to be clickable
                    nodeHighlightBehavior=True,
                    highlightColor="#F7A700", # Highlight color on hover
                    collapsible=True,
                    
                    # Add grouping/clustering option based on artist ID (not strictly needed here but useful for larger graphs)
                    # group_by=None, 
                    
                    # Configure the display options
                    display_options={"edges": {"useLabelAsTitle": True}}
                )

                # Render the graph
                agraph(
                    nodes=nodes, 
                    edges=edges, 
                    config=config
                )

                # --- Roast Generation Placeholder ---
                st.markdown("**Next:** Use the interconnected artists in your network to generate a group critique or 'roast' of your music taste.")


        except spotipy.SpotifyException as se:
            # Handle Spotify API errors
            st.error(f"Spotify API error: HTTP {getattr(se, 'http_status', 'N/A')} - {getattr(se, 'msg', str(se))}")
            st.info("Common fixes: delete the local Spotipy cache file ('.cache-*'), ensure your `.env` redirect URI matches the app settings, then re-authenticate.")
        except Exception as e:
            st.exception(e)

else:
    st.info("Click the button above to authenticate with Spotify and fetch your top tracks and visualize the network.")