from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from django.http import Http404


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, Http404):
        return Response(
            {"detail": "Страница не найдена."},
            status=status.HTTP_404_NOT_FOUND
        )

    if isinstance(exc, NotAuthenticated):
        return Response(
            {"detail": "Учетные данные не были предоставлены."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return response
