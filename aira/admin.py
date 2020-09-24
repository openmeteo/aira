from django.contrib import admin

from . import models


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    exclude = ("user",)
    list_display = (
        "user",
        "first_name",
        "last_name",
        "notification",
        "supervisor",
        "supervision_question",
    )
    search_fields = ("first_name", "last_name", "notification")
    list_filter = ("supervision_question",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        obj.save()


@admin.register(models.Agrifield)
class AgrifieldAdmin(admin.ModelAdmin):
    pass


@admin.register(models.AppliedIrrigation)
class AppliedIrrigationAdmin(admin.ModelAdmin):
    pass


class CropTypeKcStageInline(admin.TabularInline):
    model = models.CropTypeKcStage
    extra = 1


@admin.register(models.CropType)
class CropTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "fek_category",
        "max_allowed_depletion",
        "kc_plantingdate",
    )
    search_fields = ("name", "fek_category")
    list_filter = ("fek_category",)
    fields = (
        ("name",),
        ("root_depth_min", "root_depth_max"),
        ("max_allowed_depletion"),
        ("kc_offseason", "kc_plantingdate", "planting_date"),
        ("fek_category",),
    )
    inlines = [CropTypeKcStageInline]


@admin.register(models.IrrigationType)
class IrrigationTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "efficiency")
    search_fields = ("name", "efficiency")
    list_filter = ("efficiency",)
