from django.urls import path
from django.views.generic import RedirectView

from aira import views

urlpatterns = [
    path("", views.FrontPageView.as_view(), name="welcome"),
    path("home/<str:username>/", views.AgrifieldListView.as_view(), name="home"),
    path("home/", views.AgrifieldListView.as_view(), name="home"),
    # Recommendation
    path(
        "advice/<int:pk>/",
        RedirectView.as_view(permanent=True, pattern_name="recommendation"),
    ),
    path(
        "recommendation/<int:pk>/",
        views.RecommendationView.as_view(),
        name="recommendation",
    ),
    # Profile
    path(
        "update_profile/<int:pk>/",
        views.UpdateProfileView.as_view(),
        name="update_profile",
    ),
    path("delete_user/<int:pk>/", views.DeleteUserView.as_view(), name="delete_user"),
    # Agrifield
    path(
        "create_agrifield/<str:username>/",
        views.CreateAgrifieldView.as_view(),
        name="create_agrifield",
    ),
    path(
        "update_agrifield/<int:pk>/",
        views.UpdateAgrifieldView.as_view(),
        name="update_agrifield",
    ),
    path(
        "delete_agrifield/<int:pk>/",
        views.DeleteAgrifieldView.as_view(),
        name="delete_agrifield",
    ),
    path(
        "agrifield/<int:agrifield_id>/timeseries/<str:variable>/",
        views.AgrifieldTimeseriesView.as_view(),
        name="agrifield-timeseries",
    ),
    path(
        "agrifield/<int:agrifield_id>/soil_analysis/",
        views.DownloadSoilAnalysisView.as_view(),
        name="agrifield-soil-analysis",
    ),
    path(
        "create_irrigationlog/<int:pk>/",
        views.CreateAppliedIrrigationView.as_view(),
        name="create_irrlog",
    ),
    path(
        "update_irrigationlog/<int:pk>/",
        views.UpdateAppliedIrrigationView.as_view(),
        name="update_irrlog",
    ),
    path(
        "delete_irrigationlog/<int:pk>/",
        views.DeleteAppliedIrrigationView.as_view(),
        name="delete_irrlog",
    ),
    path("conversion_tools/", views.ConversionToolsView.as_view(), name="tools"),
    path("try/", views.DemoView.as_view(), name="try"),
    path(
        "irrigation-performance-chart/<int:pk>/",
        views.IrrigationPerformanceView.as_view(),
        name="irrigation-chart",
    ),
    path(
        "download-irrigation-performance/<int:pk>/",
        views.performance_csv,
        name="performance_csv",
    ),
    path(
        "supervised_user/remove/",
        views.remove_supervised_user_from_user_list,
        name="supervised_user_remove",
    ),
]
