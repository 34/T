from satchmo_store.contact.models import Contact, PhoneNumber, AddressBook
from satchmo_utils.admin import AutocompleteAdmin
from django.contrib import admin

class PhoneNumber_Inline(admin.TabularInline):
    model = PhoneNumber
    extra = 1

class AddressBook_Inline(admin.StackedInline):
    model = AddressBook
    extra = 1

class ContactOptions(AutocompleteAdmin):
    list_display = ('last_name', 'first_name')
    list_filter = ['create_date']
    ordering = ['last_name']
    search_fields = ('first_name', 'last_name', 'email')
    related_search_fields = {'user': ('username', 'first_name', 'last_name', 'email')}
    related_string_functions = {'user': lambda u: u"%s (%s)" % (u.username, u.get_full_name())}
    inlines = [PhoneNumber_Inline, AddressBook_Inline]

admin.site.register(Contact, ContactOptions)
