from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url="/")
def main_page(request):
    return render(request, "main_page.html")
