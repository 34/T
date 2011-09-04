# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
from l10n.models import Country

class AddressBook(models.Model):
    user = models.ForeignKey(User, blank=True, null=True)
    name = models.CharField(_(u'收货人'), max_length=50)
    country = models.ForeignKey(Country, null=True, verbose_name=_(u'国家'))
    province = models.CharField(_(u'省'), max_length=50)
    city = models.CharField(_(u'城市'), max_length=50)
    region = models.CharField(_(u'县/区'), max_length=50)
    stree = models.CharField(_(u'详细地址'), max_length=256)
    post_code = models.CharField(_(u'邮政编码'), max_length=10)
    phone = models.CharField(_(u'手机'), max_length=20)
    fixed_phone = models.CharField(_(u'固定电话'), max_length=30)
    is_default_shipping = models.BooleanField(_(u'默认地址'), default=False)
    
    def __unicode__(self):
        return self.name
