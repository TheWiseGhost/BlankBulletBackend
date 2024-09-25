from django.urls import path
from .views import main, add_course, course_options, course_details, update_landing

urlpatterns = [
    path('', main),
    path('course_options/', course_options),
    path('add_course/', add_course),
    path('course_details/', course_details),
    path('update_landing/', update_landing)
]
