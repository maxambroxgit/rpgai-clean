from django.urls import path
from blamPunk import views

app_name = "blamPunk"

urlpatterns = [
path('chat/', views.chat, name='chat'),
path('chatV2/', views.chat_V2, name='chat-v2'),
path('chatdark/', views.chat_V2, name='chat-dark'),
path("reset/", views.reset_session, name="reset_session"),  # 👈 questa è la chiave

]