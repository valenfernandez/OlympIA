from django.urls import path, re_path as url
from . import views

urlpatterns = [
    path("", views.home, name="analisis-home"),
    path("principal", views.principal, name="analisis-principal"),
    path("config", views.config, name="analisis-config"),
    path("carpetas", views.carpetas, name="analisis-carpetas"),
    path("carpeta/<id_carpeta>", views.carpeta, name="analisis-carpeta"),
    path("aplicacion/<id_app>", views.aplicacion, name="analisis-aplicacion"),
    path("resultados", views.resultados, name="analisis-resultados"),
    path("resultado/<id_analisis>", views.resultado, name="analisis-resultado"),
    path("nueva_carpeta", views.nueva_carpeta, name="analisis-nueva_carpeta"),
    path("borrar_archivo/<id_archivo>", views.borrar_archivo, name="analisis-borrar_archivo"),
    path("task_status/<task_id>", views.get_progress, name="task_status"),
    path("task", views.comenzar_tarea_celery, name="comenzar_tarea_celery"),
]
