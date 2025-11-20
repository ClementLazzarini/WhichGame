from . import views
from django.urls import path

urlpatterns = [
    path('', views.HomeListView.as_view(), name='home_list'),
]