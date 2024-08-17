from django.urls import path
from .views import main, add_course, course_options

urlpatterns = [
    path('', main),
    path('course_options/', course_options),
    path('add_course/', add_course),
]
