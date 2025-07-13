from django.urls import path
from ade import views

app_name = "ade"

urlpatterns = [
path('chat/', views.chat_ade, name='chat-ade'),
path("reset/", views.reset_session, name="reset_session"),  # 👈 questa è la chiave

path("load/", views.load_game_list, name="load_game_list"),
path("load/<str:filename>/", views.load_game_session, name="load_game_session"),

]