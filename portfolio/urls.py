from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import signup, home, delete_holding, delete_brazil_stock, resume, bio, projects, stocks, stocks_br_view, add_brazil_stock, edit_holding, edit_brazil_stock, general, real_estate, cash, other, vehicles, landing_view, demo_entry, exit_demo

urlpatterns = [
    path('', landing_view, name='landing'),
    path('signup/', signup, name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('demo/', demo_entry, name='demo'),
    path('demo/exit/', exit_demo, name='exit_demo'),
    path('home/', home, name='home'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('delete/<int:pk>/', delete_holding, name='delete_holding'),
    path('stocks-br/delete/<int:pk>/', delete_brazil_stock, name='delete_brazil_stock'),
    path('edit/<int:pk>/', edit_holding, name='edit_holding'),
    path('stocks-br/edit/<int:pk>/', edit_brazil_stock, name='edit_brazil_stock'),
    path('resume/', resume, name='resume'),
    path('bio/', bio, name='bio'),
    path('projects/', projects, name='projects'),
    path('stocks/', stocks, name='stocks'),
    path('stocks-br/', stocks_br_view, name='stocks_br'),
    path('stocks-br/add/', add_brazil_stock, name='add_brazil_stock'),
    path('general/', general, name='general'),
    path('real_estate/', real_estate, name='real_estate'),
    path('vehicles/', vehicles, name='vehicles'),
    path('cash/', cash, name='cash'),
    path('other/', other, name='other'),
]
