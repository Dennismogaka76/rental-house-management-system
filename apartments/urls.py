from django.urls import path
from . import views

app_name = "apartments"

urlpatterns = [
    path("", views.ApartmentListView.as_view(), name="apartment_list"),
    path("add/", views.ApartmentCreateView.as_view(), name="apartment_add"),
    path("<int:pk>/edit/", views.ApartmentUpdateView.as_view(), name="apartment_edit"),
    path("<int:pk>/delete/", views.ApartmentDeleteView.as_view(), name="apartment_delete"),

    path("rooms/", views.RoomListView.as_view(), name="room_list"),
    path("rooms/add/", views.RoomCreateView.as_view(), name="room_add"),
    path("rooms/<int:pk>/edit/", views.RoomUpdateView.as_view(), name="room_edit"),
    path("rooms/<int:pk>/delete/", views.RoomDeleteView.as_view(), name="room_delete"),
    path("api/<int:apartment_id>/vacant-rooms/", views.vacant_rooms_json, name="vacant_rooms_json"),
]
