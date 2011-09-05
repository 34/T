# coding=utf-8
from satchmo_store.contact.models import Contact, AddressBook
from satchmo_utils.admin import AutocompleteAdmin
from django.contrib import admin

class AddressBook_Inline(admin.StackedInline):
    model = AddressBook
    extra = 1

class ContactOptions(AutocompleteAdmin):
    list_display = ('name',)
    list_filter = ['create_date',]
    ordering = ['name']
    search_fields = ('name', 'email')
    related_search_fields = {'user': ('username', 'first_name', 'last_name', 'email')}
    related_string_functions = {'user': lambda u: u"%s (%s)" % (u.username, u.get_full_name())}
    inlines = [AddressBook_Inline,]

admin.site.register(Contact, ContactOptions)
