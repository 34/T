# coding=utf-8
from django import forms
from django.db.models import Q
from django.forms.extras.widgets import SelectDateWidget
from django.utils.translation import ugettext_lazy as _, ugettext
from l10n.models import Country
from livesettings import config_value
from satchmo_store.contact.models import Contact, AddressBook
from satchmo_store.shop.models import Config
from satchmo_store.shop.utils import clean_field
from signals_ahoy.signals import form_init, form_initialdata, form_postsave
import datetime
import logging
import signals

log = logging.getLogger('satchmo_store.contact.forms')

selection = ''

def area_choices_for_country(country, translator=_):
    choices = [('',translator("Not Applicable"))]

    if country:
        areas = country.adminarea_set.filter(active=True)
        if areas.count()>0:
            choices = [('',translator("---Please Select---"))]
            choices.extend([(area.abbrev or area.name, area.name) for area in areas])

    return choices

class ProxyContactForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self._contact = kwargs.pop('contact', None)
        super(ProxyContactForm, self).__init__(*args, **kwargs)

class ContactInfoForm(ProxyContactForm):
    email = forms.EmailField(max_length=75, label=_(u'邮箱'), required=True)
    title = forms.CharField(max_length=30, label=_(u'昵称'), required=False)
    name = forms.CharField(max_length=30, label=_(u'姓名'), required=False)
    sex = forms.CharField(max_length=1, label=_(u'性别'), required=False)
    phone = forms.CharField(max_length=30, label=_(u'手机'), required=False)
    fixed_phone = forms.CharField(max_length=30, label=_(u'固定电话'), required=False)
    province = forms.CharField(max_length=30, label=_(u'省'), required=False)
    city = forms.CharField(max_length=30, label=_(u'城市'), required=False)
    region = forms.CharField(max_length=100, label=_(u'县/区'))
    street = forms.CharField(max_length=30, label=_(u'详细地址'), required=False)
    postal_code = forms.CharField(max_length=10, label=_(u'邮政编码'), required=False)
    next = forms.CharField(max_length=200, widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        form_initialdata.send(self.__class__, form=self, initial=initial, contact = kwargs.get('contact', None))
        kwargs['initial'] = initial

        shop = kwargs.pop('shop', None)
        shippable = kwargs.pop('shippable', True)
        super(ContactInfoForm, self).__init__(*args, **kwargs)
        if not shop:
            shop = Config.objects.get_current()
        self._shop = shop
        self._shippable = shippable

        #self.required_billing_data = config_value('SHOP', 'REQUIRED_BILLING_DATA')
        self.required_shipping_data = config_value('SHOP', 'REQUIRED_SHIPPING_DATA')
        self._local_only = shop.in_country_only
        self.enforce_state = config_value('SHOP','ENFORCE_STATE')

        self._default_country = shop.sales_country
        shipping_country = (self._contact and getattr(self._contact.shipping_address, 'country', None)) or self._default_country
        #self.fields['country'] = forms.ModelChoiceField(shop.countries(), required=False, label=_(u'国家'), empty_label=None, initial=billing_country.pk)
        self.fields['country'] = forms.ModelChoiceField(shop.countries(), required=False, label=_(u'国家'), empty_label=None, initial=shipping_country.pk)

        if self.enforce_state:
            # if self.is_bound and not self._local_only:
            if self.is_bound and not self._local_only:
                # If the user has already chosen the country and submitted,
                # populate accordingly.
                #
                # We don't really care if country fields are empty;
                # area_choices_for_country() handles those cases properly.
                #billing_country_data = clean_field(self, 'country')
                shipping_country_data = clean_field(self, 'country')

                if shipping_country_data:
                    shipping_country = shipping_country_data

            # Get areas for the initial country selected.
            shipping_areas = area_choices_for_country(shipping_country)

            shipping_state = (self._contact and getattr(self._contact.shipping_address, 'state', None)) or selection
            self.fields['ship_state'] = forms.ChoiceField(choices=shipping_areas, initial=shipping_state, required=False, label=_(u'地区'))

        # slap a star on the required fields
        for f in self.fields:
            fld = self.fields[f]
            if fld.required:
                fld.label = (fld.label or f) + '*'
        log.info('Sending form_init signal: %s', self.__class__)
        form_init.send(self.__class__, form=self)

    def _check_state(self, data, country):
        if country and self.enforce_state and country.adminarea_set.filter(active=True, parent=None).count() > 0:
            if not data or data == selection:
                raise forms.ValidationError(
                    self._local_only and _('This field is required.') \
                               or _('State is required for your country.'))
            if (country.adminarea_set
                        .filter(active=True, parent=None)
                        .filter(Q(name__iexact=data)|Q(abbrev__iexact=data))
                        .count() != 1):
                raise forms.ValidationError(_('Invalid state or province.'))
        return data

    def clean_email(self):
        """Prevent account hijacking by disallowing duplicate emails."""
        email = self.cleaned_data.get('email', None)
        if self._contact:
            if self._contact.email and self._contact.email == email:
                return email
            users_with_email = Contact.objects.filter(email=email)
            if len(users_with_email) == 0:
                return email
            if len(users_with_email) > 1 or users_with_email[0].id != self._contact.id:
                raise forms.ValidationError(
                    ugettext("That email address is already in use."))
        return email

    def clean_postal_code(self):
        postcode = self.cleaned_data.get('postal_code')
        if not postcode:# and 'postal_code' not in self.required_billing_data:
            return postcode
        country = None

        if self._local_only:
            shop_config = Config.objects.get_current()
            country = shop_config.sales_country
        else:
            country = clean_field(self, 'country')

        if not country:
            # Either the store is misconfigured, or the country was
            # not supplied, so the country validation will fail and
            # we can defer the postcode validation until that's fixed.
            return postcode

        return self.validate_postcode_by_country(postcode, country)

    def clean_province(self):
        data = self.cleaned_data.get('province')
        if self._local_only:
            country = self._default_country
        else:
            country = clean_field(self, 'country')
            if country == None:
                raise forms.ValidationError(_('This field is required.'))
        self._check_state(data, country)
        return data

    def clean_country(self):
        if self._local_only:
            return self._default_country
        else:
            if not self.cleaned_data.get('country'):
                log.error("No country! Got '%s'" % self.cleaned_data.get('country'))
                raise forms.ValidationError(_('This field is required.'))
        return self.cleaned_data['country']

    def save(self, **kwargs):
        if not kwargs.has_key('contact'):
            kwargs['contact'] = None
        return self.save_info(**kwargs)

    def save_info(self, contact=None, **kwargs):
        """Save the contact info into the database.
        Checks to see if contact exists. If not, creates a contact
        and copies in the address and phone number."""

        if not contact:
            customer = Contact()
            log.debug('creating new contact')
        else:
            customer = contact
            log.debug('Saving contact info for %s', contact)

        data = self.cleaned_data.copy()

        country = data['country']
        if not isinstance(country, Country):
            country = Country.objects.get(pk=country)
            data['country'] = country
        data['country_id'] = country.id

        for field in customer.__dict__.keys():
            try:
                setattr(customer, field, data[field])
            except KeyError:
                pass

        customer.save()

        # we need to make sure we don't blindly add new addresses
        # this isn't ideal, but until we have a way to manage addresses
        # this will force just the two addresses, shipping and billing
        # TODO: add address management like Amazon.

        ship_address = customer.shipping_address

        form_postsave.send(ContactInfoForm, object=customer, formdata=data, form=self)

        #if changed_location:
        #    signals.satchmo_contact_location_changed.send(self, contact=customer)

        return customer.id

    def validate_postcode_by_country(self, postcode, country):
        responses = signals.validate_postcode.send(self, postcode=postcode, country=country)
        # allow responders to reformat the code, but if they don't return
        # anything, then just use the existing code
        for responder, response in responses:
            if response:
                return response

        return postcode

class DateTextInput(forms.TextInput):
    def render(self, name, value, attrs=None):
        if isinstance(value, datetime.date):
            value = value.strftime("%m.%d.%Y")
        return super(DateTextInput, self).render(name, value, attrs)

class ExtendedContactInfoForm(ContactInfoForm):
    """Contact form which includes birthday and newsletter."""
    years_to_display = range(datetime.datetime.now().year-100,datetime.datetime.now().year+1)
    dob = forms.DateField(widget=SelectDateWidget(years=years_to_display), required=False)
    newsletter = forms.BooleanField(label=_('Newsletter'), widget=forms.CheckboxInput(), required=False)
