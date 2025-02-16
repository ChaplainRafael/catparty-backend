from django.shortcuts import render,redirect
from .credentials import CLIENT_ID,CLIENT_SECRET,REDIRECT_URI
from rest_framework.views import APIView
from requests import post,Request
from rest_framework import status
from rest_framework.response import Response
from .util import *
from api.models import Room
from .models import Vote
import logging
# Create your views here.
class AuthURL(APIView):
    def get(self,request,format=None):
        scopes="user-read-playback-state user-modify-playback-state user-read-currently-playing"
         
        url= Request('GET','https://accounts.spotify.com/authorize',params={
            "scope":scopes,
            "response_type":"code",
            "redirect_uri":REDIRECT_URI,
            "client_id":CLIENT_ID
         }).prepare().url
        
        return Response({"url":url},status=status.HTTP_200_OK)


def spotify_callback(request,format=None):
    code = request.GET.get('code')
    error = request.GET.get('error')
    response = post('https://accounts.spotify.com/api/token',data={
        'grant_type':'authorization_code',
        'code':code,
        'redirect_uri':REDIRECT_URI,
        'client_id':CLIENT_ID,
        'client_secret':CLIENT_SECRET
    }).json()
    print("Token response:", response)

    access_token = response.get('access_token')
    token_type = response.get('token_type')
    expires_in = response.get('expires_in')
    refresh_token = response.get('refresh_token')
    error = response.get('error')

    if not access_token:
        return Response({'error': 'Failed to obtain access token'})

    if not request.session.exists(request.session.session_key):
        request.session.create()

    update_or_create_user_tokens(request.session.session_key,access_token,token_type,expires_in,refresh_token)

    return redirect('frontend:')

class IsAuthenticated(APIView):
    def get(self,request,format=None):
        is_authenticated= is_spotify_authenticated(self.request.session.session_key)
        return Response({'status':is_authenticated},status=status.HTTP_200_OK)


class CurrentlyPlaying(APIView):
    def get(self,request,format=None):
        room_code=self.request.session.get('room_code')
        room = Room.objects.filter(code=room_code)
        if room.exists():
            room = room[0]
        else:
            return Response({},status=status.HTTP_404_NOT_FOUND)
        session_key= room.host
        endpoint = "player/currently-playing"
        response = execute_spotify_api_request(session_key,endpoint)

        

        if "error" in response:
            # Log the error if it's found
            logging.error(f"Spotify API error: {response.get('error')}")
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        elif "item" not in response:
            # Log the response if the item is missing
            logging.warning(f"Missing 'item' in response: {response}")
            return Response({}, status=status.HTTP_204_NO_CONTENT)

        item = response.get('item')
        duration = item.get('duration_ms')
        progress = response.get('progress_ms')
        album_cover = item.get('album').get('images')[0].get('url')
        is_playing = response.get('is_playing')
        song_id = item.get('id')

        artist_string = ", ".join([artist.get('name', 'Unknown Artist') for artist in item.get('artists', []) if artist.get('name')])

        votes= len(Vote.objects.filter(room=room,song_id=song_id))
        song= {
                'title':item.get('name'),
                'artist': artist_string,
                'duration':duration,
                'time':progress,
                'image_url':album_cover,
                'is_playing': is_playing,
                'votes':votes,
                'votes_needed':room.votes_to_skip,
                'id':song_id
            }
        self.update_room_song(room,song_id)

        return Response(song,status=status.HTTP_200_OK)
    
    def update_room_song(self,room,song_id):
        current_song=room.current_song
        
        if current_song!= song_id:
            room.current_song = song_id
            room.save(update_fields=['current_song'])
            votes= Vote.objects.filter(room=room).delete()
            


    
class PauseSong(APIView):
    def put(self,request,format=None):
        room_code=self.request.session.get('room_code')
        room=Room.objects.filter(code=room_code)[0]
        if self.request.session.session_key == room.host or room.guest_can_pause:
            execute_spotify_api_request(session_key=room.host,endpoint="player/pause")
            return Response({},status=status.HTTP_204_NO_CONTENT)
        return Response({},status=status.HTTP_403_FORBIDDEN)
    
class PlaySong(APIView):
    def put(self,request,format=None):
        room_code=self.request.session.get('room_code')
        room=Room.objects.filter(code=room_code)[0]
        if self.request.session.session_key == room.host or room.guest_can_pause:
            execute_spotify_api_request(session_key=room.host,endpoint="player/play")
            return Response({},status=status.HTTP_204_NO_CONTENT)
        return Response({},status=status.HTTP_403_FORBIDDEN)
    

class SkipSong(APIView):
    def post(self,request,format=None):
        room_code = self.request.session.get('room_code')
        room = Room.objects.filter(code=room_code)[0]
        votes= Vote.objects.filter(room=room,song_id=room.current_song)
        votes_needed=room.votes_to_skip
        
        if self.request.session.session_key == room.host or len(votes)+1>= votes_needed :
            votes.delete()
            skip_song(room.host)
        else:
            vote= Vote(user=self.request.session.session_key, room=room,song_id=room.current_song)
            vote.save()
        
        return Response({},status=status.HTTP_204_NO_CONTENT)