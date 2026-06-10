from django.db import transaction
from django.db.utils import ProgrammingError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.agreement_exchange.services import (
    AgreementExchangeResolveError,
    create_change_request,
    create_or_open_exchange,
    create_or_open_from_workflow,
    exchange_detail,
    load_exchange,
    mark_viewed,
    reject_exchange,
    respond_to_request,
    restart_exchange_from_version,
    send_initial_version,
    sign_exchange,
)
from backend.agreement_exchange.templates import AGREEMENT_EXCHANGE_TEMPLATES

from .serializers import (
    AgreementExchangeCreateSerializer,
    AgreementExchangeFromWorkflowSerializer,
    AgreementExchangeRejectSerializer,
    AgreementExchangeRequestResponseSerializer,
    AgreementExchangeRequestSerializer,
    AgreementExchangeRestartSerializer,
    AgreementExchangeSignSerializer,
)


class AgreementExchangeFromWorkflowAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AgreementExchangeFromWorkflowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange = create_or_open_from_workflow(
                user=request.user,
                workflow_id=serializer.validated_data["workflow_id"],
            )
        except AgreementExchangeResolveError as exc:
            response_status = status.HTTP_403_FORBIDDEN if exc.code == "permission_denied" else status.HTTP_409_CONFLICT
            if exc.code == "workflow_not_found":
                response_status = status.HTTP_404_NOT_FOUND
            return Response({"code": exc.code, "detail": exc.message}, status=response_status)
        except ProgrammingError as exc:
            return Response({
                "code": "agreement_exchange_migration_missing",
                "detail": "Agreement Exchange database tables are missing. Run agreement_exchange migrations.",
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({
            "exchange_id": str(exchange.id),
            "redirect_url": f"/agreement-exchange/{exchange.id}",
        })


class AgreementExchangeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AgreementExchangeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exchange = create_or_open_exchange(
            user=request.user,
            contract_id=serializer.validated_data["contract_id"],
            contract_version_id=serializer.validated_data["contract_version_id"],
            counterparty_email=serializer.validated_data["counterparty_email"],
        )
        return Response(exchange_detail(exchange, request.user), status=status.HTTP_201_CREATED)


class AgreementExchangeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, exchange_id):
        exchange = load_exchange(exchange_id)
        return Response(exchange_detail(exchange, request.user))


class AgreementExchangeViewedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id):
        exchange = mark_viewed(exchange_id=exchange_id, user=request.user)
        return Response(exchange_detail(exchange, request.user))


class AgreementExchangeSendInitialAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id):
        try:
            exchange = send_initial_version(exchange_id=exchange_id, user=request.user)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(exchange_detail(exchange, request.user))


class AgreementExchangeRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exchange_id):
        serializer = AgreementExchangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange, change_request = create_change_request(
                exchange_id=exchange_id,
                user=request.user,
                validated_data=serializer.validated_data,
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            {
                "request": AgreementExchangeRequestSerializer(change_request).data,
                "exchange": exchange_detail(exchange, request.user),
            },
            status=status.HTTP_201_CREATED,
        )


class AgreementExchangeRequestRespondAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id, request_id):
        serializer = AgreementExchangeRequestResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange, change_request = respond_to_request(
                exchange_id=exchange_id,
                request_id=request_id,
                user=request.user,
                decision=serializer.validated_data["decision"],
                final_text=serializer.validated_data.get("final_text", ""),
                initiator_response=serializer.validated_data.get("initiator_response", ""),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "request": AgreementExchangeRequestSerializer(change_request).data,
            "exchange": exchange_detail(exchange, request.user),
        })


class AgreementExchangeRestartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id):
        serializer = AgreementExchangeRestartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange = restart_exchange_from_version(
                exchange_id=exchange_id,
                source_version_id=serializer.validated_data["source_version_id"],
                user=request.user,
                counterparty_email=serializer.validated_data.get("counterparty_email", ""),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({
            "exchange_id": str(exchange.id),
            "redirect_path": f"/agreement-exchange/{exchange.id}",
            "status": exchange.status,
            "current_contract": exchange_detail(exchange, request.user)["current_contract"],
        }, status=status.HTTP_201_CREATED)


class AgreementExchangeSignAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id):
        serializer = AgreementExchangeSignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange, signature = sign_exchange(
                exchange_id=exchange_id,
                user=request.user,
                typed_name=serializer.validated_data.get("typed_name", ""),
                signature_text=serializer.validated_data.get("signature_text", ""),
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"signature_id": str(signature.id), "exchange": exchange_detail(exchange, request.user)})


class AgreementExchangeRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exchange_id):
        serializer = AgreementExchangeRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exchange = reject_exchange(
                exchange_id=exchange_id,
                user=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(exchange_detail(exchange, request.user))


class AgreementExchangeTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"categories": AGREEMENT_EXCHANGE_TEMPLATES})
