from django.urls import path

from aira import views

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
