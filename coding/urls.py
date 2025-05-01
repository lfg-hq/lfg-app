from django.urls import path
from . import views

urlpatterns = [
    path('editor/', views.editor, name='editor'),
    path('get_file_tree/', views.get_file_tree, name='get_file_tree'),
    path('get_file_content/', views.get_file_content, name='get_file_content'),
    path('save_file/', views.save_file, name='save_file'),
    path('execute_command/', views.execute_command, name='execute_command'),
    path('create_folder/', views.create_folder, name='create_folder'),
    path('delete_item/', views.delete_item, name='delete_item'),
    path('rename_item/', views.rename_item, name='rename_item'),
    path('get_sandbox_info/', views.get_sandbox_info, name='get_sandbox_info'),
] 