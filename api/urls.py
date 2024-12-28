from django.urls import path
from .views import main, add_drop, drop_options, drop_details, update_landing, update_form, update_checkout, add_form_response, add_checkout_data, update_data, get_analytics, add_domain
from .views import user_details

urlpatterns = [
    path('', main),
    path('drop_options/', drop_options),
    path('add_drop/', add_drop),
    path('drop_details/', drop_details),
    path('update_landing/', update_landing),
    path('update_form/', update_form),
    path('update_checkout/', update_checkout),
    path('add_form_response/', add_form_response),
    path('add_checkout_data/', add_checkout_data),
    path('update_data/', update_data),
    path('get_analytics/', get_analytics),
    path('add_domain/', add_domain),
    path('user_details/', user_details),
]
