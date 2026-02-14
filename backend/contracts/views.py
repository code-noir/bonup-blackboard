from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse

def contract_list(request):
    return HttpResponse("Contracts are working.")
