from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import signup, home, delete_holding, root_redirect, resume, bio, projects, stocks, edit_holding, general, real_estate, cash, other, performance

urlpatterns = [
    path('', root_redirect, name='root'),
    path('signup/', signup, name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('home/', home, name='home'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('delete/<int:pk>/', delete_holding, name='delete_holding'),
    path('edit/<int:pk>/', edit_holding, name='edit_holding'),
    path('resume/', resume, name='resume'),
    path('bio/', bio, name='bio'),
    path('projects/', projects, name='projects'),
    path('stocks/', stocks, name='stocks'),
    path('general/', general, name='general'),
    path('real_estate/', real_estate, name='real_estate'),
    path('cash/', cash, name='cash'),
    path('other/', other, name='other'),
    path('performance/', performance, name='performance'),
]
