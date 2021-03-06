from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery

from wps import models

class UserProcessInline(admin.TabularInline):
    model = models.UserProcess
    extra = 0

class UserFileInline(admin.TabularInline):
    model = models.UserFile
    extra = 0

class AuthInline(admin.TabularInline):
    model = models.Auth

class JobInline(admin.TabularInline):
    model = models.Job
    extra = 0

    readonly_fields = ('status', 'updated')

    def status(self, instance):
        return instance.status_set.latest('updated_date').status

    def updated(self, instance):
        return instance.status_set.latest('updated_date').updated_date

class UserAdmin(UserAdmin):
    inlines = (
        AuthInline,
        UserFileInline,
        UserProcessInline,
        JobInline,
    )

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class OpenIDNonceAdmin(admin.ModelAdmin):
    list_display = ('server_url', 'timestamp', 'salt')

    def has_add_permission(self, request):
        return False

class OpenIDAssociationAdmin(admin.ModelAdmin):
    list_display = ('server_url', 'handle', 'issued', 'lifetime',
                    'assoc_type',)

    def has_add_permission(self, request):
        return False

admin.site.register(models.OpenIDNonce, OpenIDNonceAdmin)
admin.site.register(models.OpenIDAssociation, OpenIDAssociationAdmin)

class ServerAdmin(admin.ModelAdmin):
    list_display = ('host', 'added_date', 'status')

    def has_add_permission(self, request):
        return False

class ProcessAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'backend', 'enabled')

    def has_add_permission(self, request):
        return False

class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'host', 'variable', 'url', 'requested')

    def has_add_permission(self, request):
        return False

class CacheAdmin(admin.ModelAdmin):
    list_display = ('url', 'dimensions', 'added_date', 'accessed_date', 'size')

    def has_add_permission(self, request):
        return False

admin.site.register(models.Server, ServerAdmin)
admin.site.register(models.Process, ProcessAdmin)
admin.site.register(models.File, FileAdmin)
admin.site.register(models.Cache, CacheAdmin)
