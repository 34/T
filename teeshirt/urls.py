from django.conf.urls.defaults import patterns, url, include

from satchmo_store.urls import urlpatterns

urlpatterns += patterns('',
    url(r'captcha/', include('captcha.urls')),
)