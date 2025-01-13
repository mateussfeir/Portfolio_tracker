from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import signup, home, delete_holding, root_redirect  # Include the root_redirect view

urlpatterns = [
    path('', root_redirect, name='root'),  # Redirect based on user authentication status
    path('signup/', signup, name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('home/', home, name='home'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('delete/<int:pk>/', delete_holding, name='delete_holding'),  # Handling deletion of a holding
]
