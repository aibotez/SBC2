from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileViewSet

# 1. 创建路由器
router = DefaultRouter()
# 2. 注册视图集。r'list' 意味着访问路径将是 /api/files/list/
router.register(r'list', FileViewSet, basename='file-record')

# 3. 导出路由
urlpatterns = [
    path('', include(router.urls)),
]