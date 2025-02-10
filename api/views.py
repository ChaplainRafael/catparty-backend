from django.shortcuts import render
from rest_framework import generics,status
from .serializers import RoomSerializer,CreateRoomSerializer,UpdateRoomSerializer
from .models import Room
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
# Create your views here.
class RoomView(generics.CreateAPIView):
    queryset=Room.objects.all()
    serializer_class=RoomSerializer

from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .models import Room
from .serializers import RoomSerializer

class GetRoom(APIView):
    lookup_url_kwarg = 'code'
    serializer_class = RoomSerializer

    def get(self, request, format=None):
        code = request.GET.get(self.lookup_url_kwarg)
        
        if code is not None:
            # Fetch the room directly or return None if not found
            room = Room.objects.filter(code=code)
            
            if len(room)>0:
                data = RoomSerializer(room[0]).data
                # Check if the requester is the host
                data['is_host'] = request.session.session_key == room[0].host
                return Response(data, status=status.HTTP_200_OK)
            
            # Room with the given code was not found
            return Response({'message': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Bad request if 'code' parameter is missing
        return Response({'message': 'No code was provided'}, status=status.HTTP_400_BAD_REQUEST)



class JoinRoom(APIView):
    lookup_url_kwarg = 'code'

    def post(self, request, format=None):
        # Ensure the user has a session key
        if not request.session.exists(request.session.session_key):
            request.session.create()

        # Retrieve the room code from the request data
        code = request.data.get(self.lookup_url_kwarg)

        # Check if the code is provided
        if code:
            # Attempt to find a room with the provided code
            room_exists = Room.objects.filter(code=code).exists()
            if room_exists:
                # Set the session's room code if room exists
                request.session['room_code'] = code
                return Response({'message': 'Room found'}, status=status.HTTP_200_OK)
            
            # Respond with error if room does not exist
            return Response({'error': 'Invalid Room Code'}, status=status.HTTP_404_NOT_FOUND)

        # Respond with error if no code is provided in the request
        return Response({'error': 'Invalid post data: missing code key'}, status=status.HTTP_400_BAD_REQUEST)
        


class CreateRoomView(APIView):
    serializer_class= CreateRoomSerializer

    def post(self,request,format=None):
        if not self.request.session.exists(self.request.session.session_key):
            self.request.session.create()
        
        serializer= self.serializer_class(data=request.data)
        if serializer.is_valid():
            guest_can_pause=serializer.data.get('guest_can_pause')
            votes_to_skip=serializer.data.get('votes_to_skip')
            host=self.request.session.session_key
            query_set=Room.objects.filter(host=host)
            if query_set.exists():
                room=query_set[0]
                room.guest_can_pause=guest_can_pause
                room.votes_to_skip=votes_to_skip
                self.request.session['room_code']=room.code
                room.save(update_fields=['guest_can_pause','votes_to_skip'])
            else:
                room=Room(host=host,guest_can_pause=guest_can_pause,votes_to_skip=votes_to_skip)
                room.save()
                self.request.session['room_code']=room.code
            return Response(RoomSerializer(room).data,status=status.HTTP_201_CREATED)   
        
class UserInRoom(APIView):

    def get (self,request,format=None):
        if not self.request.session.exists(self.request.session.session_key):
            self.request.session.create()
        data={
            'code': self.request.session.get('room_code'),
        }
        return JsonResponse(data,status=status.HTTP_200_OK)

class LeaveRoom(APIView):
    def post(self,request,format=None):
        if "room_code" in self.request.session:
            self.request.session.pop("room_code")
            user_id=self.request.session.session_key
            room_result=Room.objects.filter(host=user_id).first()
            if room_result != None:
                room_result.delete()
        return Response({"Message:":"success"},status=status.HTTP_200_OK)
        
class UpdateRoom(APIView):
    serializer_class=UpdateRoomSerializer

    def patch(self,request,format=None):
        if not self.request.session.exists(self.request.session.session_key):
                self.request.session.create()
        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            guest_can_pause=serializer.data.get("guest_can_pause")
            votes_to_skip=serializer.data.get("votes_to_skip")
            code=serializer.data.get("code")
        
            host_id=self.request.session.session_key
            query_set=Room.objects.filter(code=code)
            is_host=Room.objects.filter(host=host_id)
            room = Room.objects.filter(code=code).first()
            if not query_set.exists():
                return Response({"msg":"doesn't exist!!"},status=status.HTTP_404_NOT_FOUND)
            if  room.host!=host_id:
                return Response({"msg":"You are not the host!"},status=status.HTTP_403_FORBIDDEN)
            
            room.votes_to_skip=votes_to_skip
            room.guest_can_pause=guest_can_pause
            room.save(update_fields=["guest_can_pause","votes_to_skip"])
            return Response(RoomSerializer(room).data,status=status.HTTP_200_OK)
        return Response({"Bad request":"Invalid data"},status=status.HTTP_400_BAD_REQUEST)
        