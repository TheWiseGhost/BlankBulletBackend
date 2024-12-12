from django.urls import path
from .views import main, add_bullet, bullet_options, bullet_details, update_landing, update_form, update_checkout, add_form_response, add_checkout_data, update_data, get_analytics

urlpatterns = [
    path('', main),
    path('bullet_options/', bullet_options),
    path('add_bullet/', add_bullet),
    path('bullet_details/', bullet_details),
    path('update_landing/', update_landing),
    path('update_form/', update_form),
    path('update_checkout/', update_checkout),
    path('add_form_response/', add_form_response),
    path('add_checkout_data/', add_checkout_data),
    path('update_data/', update_data),
    path('get_analytics/', get_analytics),
]
