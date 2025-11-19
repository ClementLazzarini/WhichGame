from django.shortcuts import render

def home(request):
    return render(request, 'whichgame/home.html')
