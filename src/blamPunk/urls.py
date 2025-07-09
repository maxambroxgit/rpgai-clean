from django.urls import path
from blamPunk import views

app_name = "hackergame"

urlpatterns = [
path('chatdark/', views.chat_view, name='chat-dark'),
path("reset/", views.reset_session, name="reset_session"),  # 👈 questa è la chiave

path("load/", views.load_game_list, name="load_game_list"),
path("load/<str:filename>/", views.load_game_session, name="load_game_session"),

]