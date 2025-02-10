from .models import SpotifyToken
from django.utils import timezone
from datetime import timedelta
from .credentials import CLIENT_ID,CLIENT_SECRET
from requests import post,put,get
from requests.exceptions import JSONDecodeError


BASE_URL="https://api.spotify.com/v1/me/"


def get_user_tokens(session_key):
    user_tokens=SpotifyToken.objects.filter(user=session_key)
    if user_tokens.exists():
        return user_tokens[0]
    else:
        return None

def update_or_create_user_tokens(session_key,access_token,token_type,expires_in,refresh_token):
    tokens=get_user_tokens(session_key)
    expiry = timezone.now() + timedelta(seconds=expires_in) 

    if tokens:
        tokens.access_token = access_token
        tokens.refresh_token = refresh_token
        tokens.expires_in = expiry
        tokens.token_type = token_type
        tokens.save(update_fields=["access_token","refresh_token","expires_in","token_type"])
    else:
        tokens=SpotifyToken(user=session_key,
                            access_token=access_token,
                            refresh_token=refresh_token,
                            expires_in=expiry,
                            token_type=token_type)
        tokens.save()

def is_spotify_authenticated(session_key):
    tokens = get_user_tokens(session_key)
    
    # If there are no tokens, the user is not authenticated
    if not tokens:
        return False
    
    # If the token has expired, try refreshing it
    if tokens.expires_in <= timezone.now():
        if not refresh_spotify_token(session_key):
            return False  # If token refresh fails, return False
        tokens = get_user_tokens(session_key)  # Get the updated token
    
    # Return True if the token is still valid after refreshing
    return tokens.expires_in > timezone.now()



def refresh_spotify_token(session_key):
    refresh_token = get_user_tokens(session_key).refresh_token

    response= post('https://accounts.spotify.com/api/token',data={
        'grant_type':'refresh_token',
        'refresh_token':refresh_token,
        'client_id':CLIENT_ID,
        'client_secret':CLIENT_SECRET
    }).json()

    access_token= response.get('access_token')
    token_type = response.get('token_type')
    expires_in = response.get('expires_in')
    

    update_or_create_user_tokens(session_key,access_token,token_type,expires_in,refresh_token)

def execute_spotify_api_request(session_key, endpoint, post_=False, put_=False):
    tokens = get_user_tokens(session_key)
    if not tokens:
        return {'Error': 'No tokens found'}

    headers = {'Content-type': 'application/json', 'Authorization': "Bearer " + tokens.access_token}

    # Make the appropriate request based on post_ or put_ flag
    if post_:
        response = post(BASE_URL + endpoint, headers=headers)
    elif put_:
        response = put(BASE_URL + endpoint, headers=headers)
    else:
        response = get(BASE_URL + endpoint, headers=headers)

    # Check if the response was successful
    if not response.ok:
        return {'Error': f'Failed to fetch data, status code: {response.status_code}'}

    # Check if the response is empty
    if not response.text:
        return {'Error': 'Empty response body'}
    if not response.content or response.content.strip() == b'':
        return {'Error': 'Empty response body'}
    # Try to parse the response as JSON
    try:
        return response.json()
    except JSONDecodeError as e:
        return {'Error': 'Failed to decode JSON', 'Details': str(e)}
    
#def pause_song(session_key):
    #return execute_spotify_api_request(session_key,endpoint="player/pause",put_=True)

def play_song(session_key):
    return execute_spotify_api_request(session_key,"player/play",put_=True)

def skip_song(session_key):
    return execute_spotify_api_request(session_key,"player/next", post_=True)