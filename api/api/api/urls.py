"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('api/', include('core.urls')),
    path('dashboard/', include([
        path('', TemplateView.as_view(template_name='dashboard/home.html'), name='dashboard-home'),
        path('anomalies/', TemplateView.as_view(template_name='dashboard/anomalies.html'), name='dashboard-anomalies'),
        path('correlations/', TemplateView.as_view(template_name='dashboard/correlations.html'), name='dashboard-correlations'),
        path('factors/', TemplateView.as_view(template_name='dashboard/factors.html'), name='dashboard-factors'),
        path('regression/', TemplateView.as_view(template_name='dashboard/regression.html'), name='dashboard-regression'),
        path('lags/', TemplateView.as_view(template_name='dashboard/lags.html'), name='dashboard-lags'),
        path('stress/', TemplateView.as_view(template_name='dashboard/stress.html'), name='dashboard-stress'),
    ])),
]
