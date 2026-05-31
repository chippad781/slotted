from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EventTypeViewSet, AvailabilityRuleViewSet, BlockViewSet, BookingViewSet,
    CancelBookingView, PublicProfileView, PublicSlotsView, CreateBookingView,
)

router = DefaultRouter()
router.register(r'event-types', EventTypeViewSet, basename='event-type')
router.register(r'availability-rules', AvailabilityRuleViewSet, basename='availability-rule')
router.register(r'blocks', BlockViewSet, basename='block')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('bookings/<int:pk>/cancel/', CancelBookingView.as_view(), name='booking-cancel'),

    # public
    path('public/bookings/', CreateBookingView.as_view(), name='public-create-booking'),
    path('public/<str:username>/', PublicProfileView.as_view(), name='public-profile'),
    path('public/<str:username>/<slug:event_slug>/slots/',
         PublicSlotsView.as_view(), name='public-slots'),
]
