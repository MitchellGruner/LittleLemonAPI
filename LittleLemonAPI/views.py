from datetime import date
from decimal import Decimal

from django.http import JsonResponse
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from rest_framework import generics

from .permissions import IsManager
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import permission_classes

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.decorators import throttle_classes

from django.contrib.auth.models import User, Group
from .serializers import *

# display menu items with GET request.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
class MenuItemView(generics.ListAPIView, generics.ListCreateAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    ordering_fields = ['price']
    search_fields = ['title']

    def get_permissions(self):
        permission_classes = []
        if self.request.method != 'GET':
            permission_classes = [IsAuthenticated, IsAdminUser]
        return[permission() for permission in permission_classes]

# display a single menu item based on its id.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
class SingleItemView(generics.RetrieveUpdateDestroyAPIView, generics.RetrieveAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer

    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.request.method == 'PATCH':
            permission_classes = [IsAuthenticated, IsManager | IsAdminUser]
        if self.request.method == "DELETE":
            permission_classes = [IsAuthenticated, IsAdminUser]
        return[permission() for permission in permission_classes]
    
    # menu item has opportunity to be updated with this patch function.
    def patch(self, request, *args, **kwargs):
        menuitem = MenuItem.objects.get(pk=self.kwargs['pk'])
        menuitem.featured = not menuitem.featured
        menuitem.save()
        return JsonResponse(status=200, data={'message': 'Item Has Been Updated!'})

# view the managers list.
class ManagerUsersView(generics.ListCreateAPIView):
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    queryset = User.objects.filter(groups__name='Managers')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager | IsAdminUser]

    def get_queryset(self):
        return User.objects.filter(groups=Group.objects.get(name='Manager'))

    def post(self, request, *args, **kwargs):
        if request.data['username']:
            user = get_object_or_404(User, username=request.data['username'])
            managers = Group.objects.get(name='Manager')
            managers.user_set.add(user)
            return JsonResponse(status=201, data={'message': 'User added to Managers Group!'}) 

# view a single manager in this view.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAdminUser])
class ManagerSingleUserView(generics.RetrieveDestroyAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(groups=Group.objects.get(name='Manager'))

# display the title of the categories created.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
class CategoryView(generics.ListAPIView, generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['title']

    def get_permissions(self):
        if self.request.method == 'POST':  
            return [IsAdminUser()]
        return [AllowAny()]

# display a list of all users who belong to the 'delivery crew' category.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAdminUser])
class DeliveryCrewView(generics.ListCreateAPIView):
    serializer_class = UserSerializer
    queryset = User.objects.filter(groups=Group.objects.get(name="Delivery Crew"))

    def get_queryset(self):
        delivery_group = Group.objects.get(name='Delivery Crew')
        return User.objects.filter(groups=delivery_group)

    def perform_create(self, serializer):
        delivery_group = Group.objects.get(name='Delivery Crew')
        user = serializer.save()
        user.groups.add(delivery_group)

# display a single user that is associated with the 'delivery crew' category.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAdminUser, IsManager])
class DeliveryCrewSingleUserView(generics.RetrieveDestroyAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(groups=Group.objects.get(name='Delivery Crew'))

# displays cart information tied to a particular user.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAuthenticated])
class CustomerCartView(generics.ListCreateAPIView):
    serializer_class = CartSerializer

    def get_queryset(self, *args, **kwargs):
        return Cart.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        serialized_item = AddToCartSerializer(data=request.data)
        serialized_item.is_valid(raise_exception=True)
        id = request.data['menuitem']
        quantity = request.data['quantity']
        item = get_object_or_404(MenuItem, id=id)
        price = int(quantity) * item.price
        try:
            Cart.objects.create(user=request.user, quantity=quantity, unit_price=item.price, price=price, menuitem_id=id)
        except Exception:
            return JsonResponse(data={'message': 'Item Already Exists in Cart!'})
        return JsonResponse(status=201, data={'message': 'Item Successfully Added to Cart!'})
        
    def delete(self, request):
        user = self.request.user
        Cart.objects.filter(user=user).delete()
        return Response(status=204)

# display orders associated with a manager of delivery crew member.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAuthenticated])
class OrdersView(generics.ListCreateAPIView):
    serializer_class = OrdersSerializer
        
    def get_queryset(self, *args, **kwargs):
        if self.request.user.groups.filter(name='Manager').exists() or self.request.user.is_superuser == True:
            query = Order.objects.all()
        elif self.request.user.groups.filter(name='Delivery Crew').exists():
            query = Order.objects.filter(delivery_crew=self.request.user)
        else:
            query = Order.objects.filter(user=self.request.user)
        return query

    def get_permissions(self):
        if self.request.method == 'GET' or 'POST': 
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsManager | IsAdminUser]
        return[permission() for permission in permission_classes]

    def post(self, request, *args, **kwargs):
        cart_items = Cart.objects.filter(user=request.user)
        total = self.calculate_total(cart_items)
        order = Order.objects.create(user=request.user, status=False, total=total, date=date.today())
        for i in cart_items.values():
            menuitem = get_object_or_404(MenuItem, id=i['menuitem_id'])
            orderitem = OrderItem.objects.create(order=order, menuitem=menuitem, quantity=i['quantity'])
            orderitem.save()
        cart_items.delete()
        return JsonResponse(status=201, data={'message': 'Order Has Been Placed!'})

    def calculate_total(self, cart_items):
        total = Decimal(0)
        for item in cart_items:
            total += item.price
        return total

# displays a single order.
@throttle_classes([AnonRateThrottle, UserRateThrottle])
@permission_classes([IsAuthenticated])
class SingleOrderView(generics.ListCreateAPIView):
    serializer_class = SingleOrderSerializer

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Manager').exists():
            return Order.objects.all()
        return Order.objects.filter(user=user)