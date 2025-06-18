# Create your views here.

from django.shortcuts import render


def fov_calculator(request):
    """FOV Calculator view for sim racing setups."""
    context = {
        "title": "FOV Calculator",
        "description": "Calculate your optimal Field of View for sim racing setups",
    }
    return render(request, "sim/fov_calculator.html", context)
