from django.urls import path
from .views import *

urlpatterns = [
    path('menu-items/', MenuItemView.as_view()),
    path('menu-items/<int:pk>/', SingleItemView.as_view()),
    path('groups/manager/users/', ManagerUsersView.as_view()),
    path('groups/manager/users/<int:pk>/', ManagerSingleUserView.as_view()),
    path('menu-items/category/', CategoryView.as_view()),
    path('groups/delivery-crew/users/', DeliveryCrewView.as_view()),
    path('groups/delivery-crew/users/<int:pk>/', DeliveryCrewSingleUserView.as_view()),
    path('cart/menu-items/', CustomerCartView.as_view()),
    path('orders/', OrdersView.as_view()),
    path('orders/<int:pk>/', SingleOrderView.as_view()),
]