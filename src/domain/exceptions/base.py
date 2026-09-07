"""
CampusGrid AI: Domain Exception Hierarchy
Structured exception classes for domain, business logic, provider, and constraint errors.
"""

from typing import Dict, Any, Optional

class DomainException(Exception):
    """Base exception for all domain and application errors."""
    def __init__(
        self,
        message: str,
        error_code: str = "DOMAIN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }

class ProviderException(DomainException):
    """Raised when an external infrastructure provider fails."""
    def __init__(self, message: str, provider_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"[{provider_name}] {message}",
            error_code="PROVIDER_ERROR",
            details={"provider": provider_name, **(details or {})}
        )

class LLMProviderException(ProviderException):
    """Raised when an LLM provider encounters rate limits, timeouts, or API errors."""
    def __init__(self, message: str, provider_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, provider_name=provider_name, details=details)
        self.error_code = "LLM_PROVIDER_ERROR"

class VectorStoreException(ProviderException):
    """Raised when a vector database operation fails."""
    def __init__(self, message: str, provider_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, provider_name=provider_name, details=details)
        self.error_code = "VECTOR_STORE_ERROR"

class InfeasibleOptimizationError(DomainException):
    """Raised when the MILP dispatch solver cannot find a feasible mathematical solution."""
    def __init__(self, message: str = "Mathematical optimization model is infeasible under given constraints", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, error_code="OPTIMIZATION_INFEASIBLE", details=details)

class SafetyViolationError(DomainException):
    """Raised when a suggested action violates physical safety guardrails (ASHRAE-55 or Battery SOC)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, error_code="SAFETY_GUARDRAIL_VIOLATION", details=details)

class EntityNotFoundError(DomainException):
    """Raised when a requested domain entity or record is not found."""
    def __init__(self, entity_type: str, identifier: Any):
        super().__init__(
            message=f"{entity_type} with identifier '{identifier}' was not found.",
            error_code="ENTITY_NOT_FOUND",
            details={"entity_type": entity_type, "identifier": str(identifier)}
        )

class ToolExecutionError(DomainException):
    """Raised when an agent tool or MCP action fails during execution."""
    def __init__(self, tool_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {message}",
            error_code="TOOL_EXECUTION_ERROR",
            details={"tool_name": tool_name, **(details or {})}
        )

class FaithfulnessVerificationError(DomainException):
    """Raised when generated XAI justification fails automated factual alignment against solver numbers."""
    def __init__(self, ungrounded_claims: list, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"XAI explanation contains ungrounded claims not present in solver logs: {ungrounded_claims}",
            error_code="FAITHFULNESS_CHECK_FAILED",
            details={"ungrounded_claims": ungrounded_claims, **(details or {})}
        )
