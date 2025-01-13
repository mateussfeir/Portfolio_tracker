from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import signup, home, delete_holding  # Import the delete_holding view

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('home/', home, name='home'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),  # Ensure 'next_page' is set to 'login'
    path('delete/<int:pk>/', delete_holding, name='delete_holding'),  # Add this line for holding deletion
]
