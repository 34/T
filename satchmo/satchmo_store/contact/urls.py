"""
URLConf for Satchmo Contacts.
"""

from django.conf.urls.defaults import patterns
from signals_ahoy.signals import collect_urls
from satchmo_store import contact

urlpatterns = patterns('satchmo_store.contact.views',
    (r'^$', 'view', {}, 'satchmo_account_info'),
    (r'^update/$', 'update', {}, 'satchmo_profile_update'),
    (r'^ajax_state/$', 'ajax_get_state', {}, 'satchmo_contact_ajax_state'),
    (r'^add_addressbook/$', 'add_addressbook', {}, 'satchmo_addressbook_add'),
    (r'^ajax_get_sub_areas/$', 'ajax_get_sub_areas', {}, 'satchmo_ajax_get_sub_areas'),
    
)

collect_urls.send(sender=contact, patterns=urlpatterns)
