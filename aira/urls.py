from django.urls import path
from django.views.generic import RedirectView

from aira import obsolete_redirected_views, views

urlpatterns = [
    path("", views.FrontPageView.as_view(), name="frontpage"),
    path(
        "<str:username>/fields/",
        views.AgrifieldListView.as_view(),
        name="agrifield-list",
    ),
    path("myfields/", views.MyFieldsView.as_view(), name="my_fields"),
    path(
        "<str:username>/fields/<int:pk>/report/",
        views.AgrifieldReportView.as_view(),
        name="agrifield-report",
    ),
    path(
        "<str:username>/fields/create/",
        views.CreateAgrifieldView.as_view(),
        name="agrifield-create",
    ),
    path(
        "<str:username>/fields/<int:pk>/edit/",
        views.UpdateAgrifieldView.as_view(),
        name="agrifield-update",
    ),
    path(
        "<str:username>/fields/<int:pk>/delete/",
        views.DeleteAgrifieldView.as_view(),
        name="agrifield-delete",
    ),
    path(
        "<str:username>/fields/<int:agrifield_id>/timeseries/<str:variable>/",
        views.AgrifieldTimeseriesView.as_view(),
        name="agrifield-timeseries",
    ),
    path(
        "<str:username>/fields/<int:agrifield_id>/soil_analysis/",
        views.DownloadSoilAnalysisView.as_view(),
        name="agrifield-soil-analysis",
    ),
    path(
        "<str:username>/fields/<int:agrifield_id>/appliedirrigations/",
        views.AppliedIrrigationsView.as_view(),
        name="applied-irrigations",
    ),
    path(
        "<str:username>/fields/<int:agrifield_id>/appliedirrigations/<int:pk>/edit/",
        views.UpdateAppliedIrrigationView.as_view(),
        name="applied-irrigation-update",
    ),
    path(
        "<str:username>/fields/<int:agrifield_id>/appliedirrigations/<int:pk>/delete/",
        views.DeleteAppliedIrrigationView.as_view(),
        name="applied-irrigation-delete",
    ),
    path(
        "<str:username>/fields/<int:pk>/performance/",
        views.IrrigationPerformanceView.as_view(),
        name="agrifield-irrigation-performance",
    ),
    path(
        "<str:username>/fields/<int:pk>/performance/download/",
        views.IrrigationPerformanceCsvView.as_view(),
        name="agrifield-irrigation-performance-download",
    ),
    path(
        "<str:username>/supervisees/remove/",
        views.remove_supervisee_from_user_list,
        name="supervisee-remove",
    ),
    path(
        "<str:username>/supervisees/",
        views.SuperviseesView.as_view(),
        name="supervisees",
    ),
    path("conversion_tools/", views.ConversionToolsView.as_view(), name="tools"),
    path("try/", views.DemoView.as_view(), name="try"),
]

redirections_of_old_urls = [
    path(
        "home/<str:username>/",
        RedirectView.as_view(permanent=True, pattern_name="agrifield-list"),
    ),
    path("home/", RedirectView.as_view(permanent=True, pattern_name="my_fields")),
    path(
        "advice/<int:pk>/",
        obsolete_redirected_views.RecommendationRedirectView.as_view(),
    ),
    path(
        "recommendation/<int:pk>/",
        obsolete_redirected_views.RecommendationRedirectView.as_view(),
    ),
    path(
        "create_agrifield/<str:username>/",
        RedirectView.as_view(permanent=True, pattern_name="agrifield-create"),
    ),
    path(
        "update_agrifield/<int:pk>/",
        obsolete_redirected_views.UpdateAgrifieldRedirectView.as_view(),
    ),
    path(
        "delete_agrifield/<int:pk>/",
        obsolete_redirected_views.DeleteAgrifieldRedirectView.as_view(),
    ),
    path(
        "agrifield/<int:agrifield_id>/timeseries/<str:variable>/",
        obsolete_redirected_views.AgrifieldTimeseriesRedirectView.as_view(),
    ),
    path(
        "agrifield/<int:agrifield_id>/soil_analysis/",
        obsolete_redirected_views.DownloadSoilAnalysisRedirectView.as_view(),
    ),
    path(
        "create_irrigationlog/<int:pk>/",
        obsolete_redirected_views.AppliedIrrigationsRedirectView.as_view(),
    ),
    path(
        "update_irrigationlog/<int:pk>/",
        obsolete_redirected_views.AppliedIrrigationEditRedirectView.as_view(),
    ),
    path(
        "delete_irrigationlog/<int:pk>/",
        obsolete_redirected_views.AppliedIrrigationDeleteRedirectView.as_view(),
    ),
    path(
        "irrigation-performance-chart/<int:pk>/",
        obsolete_redirected_views.IrrigationPerformanceRedirectView.as_view(),
    ),
    path(
        "download-irrigation-performance/<int:pk>/",
        obsolete_redirected_views.IrrigationPerformanceDownloadRedirectView.as_view(),
    ),
]

urlpatterns.extend(redirections_of_old_urls)
