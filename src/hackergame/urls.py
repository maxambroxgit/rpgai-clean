from django.urls import path
from hackergame import views

app_name = "hackergame"

urlpatterns = [
path('chat/', views.chat_view, name='hackergame-chat'),
path("reset/", views.reset_session, name="reset_session"),  # 👈 questa è la chiave

path("load/", views.load_game_list, name="load_game_list"),
path("load/<str:filename>/", views.load_game_session, name="load_game_session"),

]