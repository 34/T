# coding=utf-8
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from satchmo_store.shop.models import Order, Cart, Config
from satchmo_store.contact.models import Contact
from satchmo_utils.views import bad_or_missing

from signals_ahoy.signals import form_initialdata
from livesettings import config_get_group, config_value

from satchmo_store.contact.forms import AddressBookForm, ShippingMethodForm, PaymentMethodForm

def success(request):
    """
    The order has been succesfully processed.  This can be used to generate a receipt or some other confirmation
    """
    try:
        order = Order.objects.from_request(request)
    except Order.DoesNotExist:
        return bad_or_missing(request, _('Your order has already been processed.'))

    del request.session['orderID']
    return render_to_response('shop/checkout/success.html',
                              {'order': order},
                              context_instance=RequestContext(request))
success = never_cache(success)

def failure(request):
    return render_to_response(
        'shop/checkout/failure.html',
        {},
        context_instance=RequestContext(request)
    )

def confirm_order_info(request, template=None):
    '''确认订单信息'''
    
    #First verify that the cart exists and has items
    tempCart = Cart.objects.from_request(request)
    if tempCart.numItems == 0:
        return render_to_response('shop/checkout/empty_cart.html',
                                  context_instance=RequestContext(request))

    if not request.user.is_authenticated() and config_value('SHOP', 'AUTHENTICATION_REQUIRED'):
        url = urlresolvers.reverse('satchmo_checkout_auth_required')
        thisurl = urlresolvers.reverse('satchmo_checkout-step1')
        return http.HttpResponseRedirect(url + "?next=" + thisurl)
    
    init_data = {}
    shop = Config.objects.get_current()
    try:
        contact = Contact.objects.from_request(request, create=True)
        init_data['contact'] = contact.id
    except Contact.DoesNotExist:
        contact = None
    
    order = None
    try:
        order = Order.objects.from_request(request)
        if order.discount_code:
            init_data['discount'] = order.discount_code
    except Order.DoesNotExist:
        pass
    
    if request.method == "POST":
        pass
    else:
        if contact:
            if contact.shipping_address:
                for item in contact.shipping_address.__dict__.keys():
                    init_data[item] = getattr(contact.shipping_address,item)
            
            
        else:
            # Allow them to login from this page.
            request.session.set_test_cookie()
        
        #Request additional init_data
        form_initialdata.send(sender=AddressBookForm, initial=init_data,
            contact=contact, cart=tempCart, shop=shop)
        
        form = AddressBookForm(
            shop=shop,
            contact=contact,
            initial=init_data)
        
        ship_form = ShippingMethodForm()
        payment_form = PaymentMethodForm()
        
    if shop.in_country_only:
        only_country = shop.sales_country
    else:
        only_country = None
    
    
    
    context = RequestContext(request, {
        'form': form,
        'ship_form': ship_form,
        'payment_form': payment_form,
        'country': only_country,
        'contact': contact,
        'addressbooklist': contact.addressbook_set.all(),
        'order': order,
        #'paymentmethod_ct': len(form.fields['paymentmethod'].choices)
        })
    
    return render_to_response('shop/checkout/form.html',
                              context_instance=context)