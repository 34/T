# coding=utf-8
"""
Stores customer, organization, and order information.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
from l10n.models import Country
from satchmo_store.contact import CUSTOMER_ID
import datetime
import logging

log = logging.getLogger('contact.models')

class ContactManager(models.Manager):

    def from_request(self, request, create=False):
        """Get the contact from the session, else look up using the logged-in
        user. Create an unsaved new contact if `create` is true.

        Returns:
        - Contact object or None
        """

        contact = None
        if request.user.is_authenticated():
            try:
                contact = Contact.objects.get(user=request.user.id)
                request.session[CUSTOMER_ID] = contact.id
            except Contact.DoesNotExist:
                pass
        else:
            # Don't create a Contact if the user isn't authenticated.
            create = False
            
        if request.session.get(CUSTOMER_ID):
            try:
                contactBySession = Contact.objects.get(id=request.session[CUSTOMER_ID])
                if contact is None:
                    contact = contactBySession
                elif contact != contactBySession:
                    # For some reason the authenticated id and the session customer ID don't match.
                    # Let's bias the authenticated ID and kill this customer ID:
                    log.debug("CURIOUS: The user authenticated as %r (contact id:%r) and a session as %r (contact id:%r)" %
                               (contact.user.get_full_name(), contact.id, Contact.objects.get(id=request.session[CUSTOMER_ID]).full_name, request.session[CUSTOMER_ID]))
                    log.debug("Deleting the session contact.")
                    del request.session[CUSTOMER_ID]
            except Contact.DoesNotExist:
                log.debug("This user has a session stored customer id (%r) which doesn't exist anymore. Removing it from the session." % request.session[CUSTOMER_ID])
                del request.session[CUSTOMER_ID]

        if contact is None:
            if create:
                contact = Contact(user=request.user)

            else:
                raise Contact.DoesNotExist()

        return contact


class Contact(models.Model):
    """
    A customer, supplier or any individual that a store owner might interact
    with.
    """
    title = models.CharField(_(u"昵称"), max_length=30, blank=True, null=True)
    name = models.CharField(_(u"姓名"), max_length=30, )
    user = models.ForeignKey(User, blank=True, null=True, unique=True, verbose_name=_(u"用户"))
    dob = models.DateField(_(u"生日"),blank=True, null=True)
    phone = models.CharField(_(u"手机"), max_length=30, blank=True, null=True)
    fixed_phone = models.CharField(_(u"固定电话"), max_length=30, blank=True, null=True)
    email = models.EmailField(_(u"邮箱"), blank=True, max_length=75)
    notes = models.TextField(_(u"备注"), max_length=500, blank=True)
    create_date = models.DateField(_(u"创建日期"))

    objects = ContactManager()

    def _get_full_name(self):
        """Return the person's full name."""
        return u'%s' % self.name
    full_name = property(_get_full_name)

    def _shipping_address(self):
        """Return the default shipping address or None."""
        try:
            return self.addressbook_set.get(is_default_shipping=True)
        except AddressBook.DoesNotExist:
            return None
    shipping_address = property(_shipping_address)

    def _primary_phone(self):
        """Return the default phone number or None."""
        return self.phone
    primary_phone = property(_primary_phone)

    def __unicode__(self):
        return self.full_name

    def save(self, **kwargs):
        """Ensure we have a create_date before saving the first time."""
        if not self.pk:
            self.create_date = datetime.date.today()
        # Validate contact to user sync
        if self.user:
            dirty = Falses
            user = self.user
            if user.email != self.email:
                user.email = self.email
                dirty = True

            if user.username != self.name:
                user.username = self.name
                dirty = True

            if dirty:
                self.user = user
                self.user.save()

        super(Contact, self).save(**kwargs)

    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")

class AddressBook(models.Model):
    """
    Address information associated with a contact.
    """
    contact = models.ForeignKey(Contact)
    name = models.CharField(_(u'收货人'), max_length=50)
    country = models.ForeignKey(Country, null=True, verbose_name=_(u'国家'))
    province = models.CharField(_(u'省'), max_length=50)
    city = models.CharField(_(u'城市'), max_length=50)
    region = models.CharField(_(u'县/区'), max_length=100)
    street = models.CharField(_(u'详细地址'), max_length=256)
    postal_code = models.CharField(_(u'邮政编码'), max_length=10)
    phone = models.CharField(_(u'手机'), max_length=20)
    fixed_phone = models.CharField(_(u'固定电话'), max_length=30)
    is_default_shipping = models.BooleanField(_(u'默认地址'), default=False)

    def __unicode__(self):
       return u'%s' % self.name

    def save(self, **kwargs):
        """
        假如这个地址是默认地址，那么就会移除旧地址的默认地址属性。
        如果还没有默认地址，那么就将这个地址设为默认地址。
        """
        existing_shipping = self.contact.shipping_address
        if existing_shipping:
            if self.is_default_shipping:
                existing_shipping.is_default_shipping = False
                super(AddressBook, existing_shipping).save()
        else:
            self.is_default_shipping = True

        super(AddressBook, self).save(**kwargs)

    class Meta:
        verbose_name = _("Address")
        verbose_name_plural = _("Addressee")

import config
