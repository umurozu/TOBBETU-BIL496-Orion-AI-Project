"""
DownloadController — LLD §3.1.2, Class: DownloadController
HLD Module: Controller Layer — Export

Responsible for exporting processed images into the desired format
and initiating download operations.
"""

import io
import logging

from app.model.result_image import ResultImage, ExportFormat
from app.services.session_service import SessionService
from app.services.export_service import ExportService
from app.controller.session_controller import SessionController
from app.controller.security_controller import SecurityController
from app.utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DownloadController:
    """
    LLD §3.1.2 — Class DownloadController

    Attributes:
        sessionController: Retrieves processed image from session
        securityController: Ensures secure download request
    """

    def __init__(
        self,
        session_service: SessionService,
        session_controller: SessionController,
        security_controller: SecurityController,
        export_service: ExportService,
    ):
        self.sessionService = session_service
        self.sessionController = session_controller
        self.securityController = security_controller
        self.exportService = export_service

    def prepareDownload(self, session_id: str, format_str: str = "png") -> tuple:
        """
        Prepares processed image for export.
        
        Args:
            session_id: Session ID.
            format_str: Export format string (jpeg, png, webp).
            
        Returns:
            Tuple of (image_bytes, content_type, filename).
        """
        self.sessionController.validateSession(session_id)

        result = self.sessionService.getResult(session_id)
        if result is None:
            raise ValidationError(
                message="No processed image available. Run an editing operation first.",
                error_code="NO_RESULT",
            )

        export_format = self._parseFormat(format_str)
        converted_bytes = self._convertFormat(result, export_format)

        content_type_map = {
            ExportFormat.JPEG: "image/jpeg",
            ExportFormat.PNG: "image/png",
            ExportFormat.WEBP: "image/webp",
        }

        extension_map = {
            ExportFormat.JPEG: "jpg",
            ExportFormat.PNG: "png",
            ExportFormat.WEBP: "webp",
        }

        content_type = content_type_map[export_format]
        filename = f"invisio_result.{extension_map[export_format]}"

        return converted_bytes, content_type, filename

    def _convertFormat(self, image: ResultImage, export_format: ExportFormat) -> bytes:
        """Converts image into selected format through the export pipeline."""
        return self.exportService.exportResult(image, export_format)

    def _parseFormat(self, format_str: str) -> ExportFormat:
        """Converts string to ExportFormat enum."""
        fmt = format_str.lower().strip()
        format_map = {
            "jpeg": ExportFormat.JPEG,
            "jpg": ExportFormat.JPEG,
            "png": ExportFormat.PNG,
            "webp": ExportFormat.WEBP,
        }
        if fmt not in format_map:
            raise ValidationError(
                message=f"Unsupported export format: '{fmt}'. Supported: jpeg, png, webp",
                error_code="INVALID_FORMAT",
            )
        return format_map[fmt]
