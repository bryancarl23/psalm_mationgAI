from django.urls import path
from . import views

urlpatterns = [
	path("", views.home_view, name="home"),
	path("about/", views.about_view, name="about"),
	path("products/", views.products_view, name="products"),
	path("marketing/", views.marketing_view, name="marketing"),
	path("contact/", views.contact_view, name="contact"),
	path("chatbot/", views.chatbot_view, name="chatbot"),
]


