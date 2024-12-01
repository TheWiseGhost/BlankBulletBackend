from django.urls import path
from .views import main, add_bullet, bullet_options, bullet_details, update_landing, update_form, update_checkout

urlpatterns = [
    path('', main),
    path('bullet_options/', bullet_options),
    path('add_bullet/', add_bullet),
    path('bullet_details/', bullet_details),
    path('update_landing/', update_landing),
    path('update_form/', update_form),
    path('update_checkout/', update_checkout),
]
