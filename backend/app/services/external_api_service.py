"""
External API verification service.

Real integrations (MCA21, GST portal, RBI IFSC, penny drop) are not yet wired up.
The pipeline stage is cleanly skipped so it does not produce false pass/fail signals.
When real API keys are available, replace this module with actual HTTP calls.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_external_verifications(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder — external registry verification is disabled.
    Returns skipped so the pipeline stage records a 'skipped' status without
    adding any spurious pass/fail checks to the validation results.
    """
    logger.info("External verification skipped — real API integrations not yet configured")
    return {
        "skipped": True,
        "reason": "External API verification not yet configured (MCA21, GST portal, IFSC, penny drop)",
    }
