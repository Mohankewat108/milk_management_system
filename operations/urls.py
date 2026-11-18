from django.urls import path

from . import views

urlpatterns = [
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/new/', views.collection_create, name='collection_create'),
    path('branches/new/', views.branch_create, name='branch_create'),
    path('pricing/new/', views.pricing_create, name='pricing_create'),
    path('farmers/', views.farmer_list, name='farmer_list'),
    path('farmers/new/', views.farmer_create, name='farmer_create'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/new/', views.staff_create, name='staff_create'),
    path('payments/new/', views.payment_create, name='payment_create'),
    path('expenses/new/', views.expense_create, name='expense_create'),
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('support/', views.support_list, name='support_list'),
    path('customer-portal/', views.customer_portal, name='customer_portal'),
    path('reports/collections.csv/', views.collections_csv, name='collections_csv'),
]
