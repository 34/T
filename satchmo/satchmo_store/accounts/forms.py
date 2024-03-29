# coding=utf-8
from django import forms
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _, ugettext
from satchmo_store.accounts.mail import send_welcome_email
from livesettings import config_value
from satchmo_store.contact.forms import ContactInfoForm
from satchmo_store.contact.models import Contact
from satchmo_utils.unique_id import generate_id
from signals_ahoy.signals import form_init, form_initialdata
from satchmo_store.accounts.models import AddressBook
from captcha.fields import CaptchaField

import logging
import signals

log = logging.getLogger('accounts.forms')

class AddressBookForm(forms.ModelForm):
    class Meta:
        model = AddressBook

class EmailAuthenticationForm(AuthenticationForm):
    """Authentication form with a longer username field."""

    def __init__(self, *args, **kwargs):

        super(EmailAuthenticationForm, self).__init__(*args, **kwargs)
        username = self.fields['username']
        username.max_length = 75
        username.widget.attrs['maxlength'] = 75

class RegistrationForm(forms.Form):
    """The basic account registration form."""
    title = forms.CharField(max_length=30, label=_('Title'), required=False)
    email = forms.EmailField(label=_(u'Email地址'),
        max_length=75, required=True)
    password2 = forms.CharField(label=_(u'确认密码'),
        max_length=30, widget=forms.PasswordInput(), required=True)
    password1 = forms.CharField(label=_(u'登陆密码'),
        max_length=30, widget=forms.PasswordInput(), required=True)
    username = forms.CharField(label=_(u'用户名'),
        max_length=30, required=True)
    captcha = CaptchaField(label=_(u'验证码'))
    next = forms.CharField(max_length=200, required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        contact = kwargs.get('contact', None)
        initial = kwargs.get('initial', {})
        self.contact = contact
        form_initialdata.send(self.__class__,
            form=self,
            contact=contact,
            initial=initial)

        kwargs['initial'] = initial
        super(RegistrationForm, self).__init__(*args, **kwargs)
        form_init.send(self.__class__,
            form=self,
            contact=contact)

    newsletter = forms.BooleanField(label=_(u'订阅邮件'),
        widget=forms.CheckboxInput(), required=False)

    def clean_password1(self):
        """Enforce that password and password2 are the same."""
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if not (p1 and p2 and p1 == p2):
            raise forms.ValidationError(
                ugettext(u"两次输入的密码不匹配！"))

        # note, here is where we'd put some kind of custom
        # validator to enforce "hard" passwords.
        return p1

    def clean_email(self):
        """Prevent account hijacking by disallowing duplicate emails."""
        email = self.cleaned_data.get('email', None)
        if email and User.objects.filter(email__iexact=email).count() > 0:
            raise forms.ValidationError(
                ugettext(u"您输入的邮箱已处在！"))

        return email

    def clean_username(self):
        """防止用户名重复"""
        username = self.cleaned_data.get('username', None)
        if username and User.objects.filter(username=username).count() > 0:
            raise forms.ValidationError(
                ugettext(u"该用户名已经被使用."))

        return username

    def save(self, request=None, **kwargs):
        """Create the contact and user described on the form.  Returns the
        `contact`.
        """
        if self.contact:
            log.debug('skipping save, already done')
        else:
            self.save_contact(request)
        return self.contact

    def save_contact(self, request):
        log.debug("Saving contact")
        data = self.cleaned_data
        password = data['password1']
        email = data['email']
        username = data['username']

        verify = (config_value('SHOP', 'ACCOUNT_VERIFICATION') == 'EMAIL')

        if verify:
            site = Site.objects.get_current()
            from registration.models import RegistrationProfile
            # TODO:
            # In django-registration trunk this signature has changed.
            # Satchmo is going to stick with the latest release so I'm changing
            # this to work with 0.7
            # When 0.8 comes out we're going to have to refactor to this:
            #user = RegistrationProfile.objects.create_inactive_user(
            #    username, email, password, site)
            # See ticket #1028 where we checked in the above line prematurely
            user = RegistrationProfile.objects.create_inactive_user(username, '',
                    password, email)
        else:
            user = User.objects.create_user(username, email, password)

        user.save()

        # If the user already has a contact, retrieve it.
        # Otherwise, create a new one.
        try:
            contact = Contact.objects.from_request(request, create=False)

        except Contact.DoesNotExist:
            contact = Contact()

        contact.user = user
        contact.name = username
        contact.email = email
        contact.title = data.get('title', '')
        contact.save()

        if 'newsletter' not in data:
            subscribed = False
        else:
            subscribed = data['newsletter']

        signals.satchmo_registration.send(self, contact=contact, subscribed=subscribed, data=data)

        if not verify:
            user = authenticate(username=username, password=password)
            login(request, user)
            send_welcome_email(email, username, '')
            signals.satchmo_registration_verified.send(self, contact=contact)

        self.contact = contact

        return contact

class RegistrationAddressForm(RegistrationForm, ContactInfoForm):
    """Registration form which also requires address information."""

    def __init__(self, *args, **kwargs):
        super(RegistrationAddressForm, self).__init__(*args, **kwargs)

    def save(self, request=None, **kwargs):
        contact = self.save_contact(request)
        kwargs['contact'] = contact

        log.debug('Saving address for %s', contact)
        self.save_info(**kwargs)

        return contact
