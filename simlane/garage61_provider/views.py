"""OAuth2 views for Garage61 provider"""

from allauth.socialaccount.providers.oauth2.views import OAuth2CallbackView
from allauth.socialaccount.providers.oauth2.views import OAuth2LoginView

from .adapter import Garage61OAuth2Adapter

oauth2_login = OAuth2LoginView.adapter_view(Garage61OAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(Garage61OAuth2Adapter)
