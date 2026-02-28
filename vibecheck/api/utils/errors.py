class VibeCheckError(Exception):
    def __init__(
        self,
        type: str,
        message: str,
        code: str,
        status_code: int,
        param: str | None = None,
    ):
        self.type = type
        self.message = message
        self.code = code
        self.status_code = status_code
        self.param = param

    @classmethod
    def not_found(cls, resource: str, id: str):
        return cls(
            "not_found",
            f"{resource} '{id}' not found.",
            f"{resource.upper()}_NOT_FOUND",
            404,
        )

    @classmethod
    def invalid_mode(cls):
        return cls(
            "validation_error",
            "Mode must be 'lightweight' or 'robust'.",
            "INVALID_MODE",
            400,
            "mode",
        )

    @classmethod
    def missing_repo_url(cls):
        return cls(
            "validation_error",
            "Lightweight mode requires 'repo_url' or 'files'.",
            "MISSING_REPO_URL",
            400,
        )

    @classmethod
    def missing_tunnel_session(cls):
        return cls(
            "validation_error",
            "Robust mode requires 'tunnel_session_id'.",
            "MISSING_TUNNEL_SESSION",
            400,
        )

    @classmethod
    def tunnel_not_connected(cls):
        return cls(
            "tunnel_error",
            "Tunnel session is not connected. Run 'vibecheck connect <port>' first.",
            "TUNNEL_NOT_CONNECTED",
            400,
        )

    @classmethod
    def invalid_agent(cls, name: str):
        return cls(
            "validation_error",
            f"Unknown agent '{name}'. Valid agents: recon, auth, injection, config.",
            "INVALID_AGENT",
            400,
            "agents",
        )

    @classmethod
    def assessment_in_progress(cls):
        return cls(
            "conflict",
            "Assessment is still in progress. Wait for completion before re-running.",
            "ASSESSMENT_IN_PROGRESS",
            400,
        )

    @classmethod
    def logs_not_available(cls):
        return cls(
            "validation_error",
            "Agent logs are only available for robust mode assessments.",
            "LOGS_NOT_AVAILABLE",
            400,
        )

    @classmethod
    def clone_failed(cls, url: str, reason: str):
        return cls(
            "external_error",
            f"Failed to clone '{url}': {reason}",
            "CLONE_FAILED",
            502,
        )

    @classmethod
    def duplicate_idempotency_key(cls):
        return cls(
            "conflict",
            "Idempotency key already used with different parameters.",
            "DUPLICATE_IDEMPOTENCY_KEY",
            409,
        )

    @classmethod
    def target_unreachable(cls):
        return cls(
            "tunnel_error",
            "Could not reach target application through tunnel.",
            "TARGET_UNREACHABLE",
            502,
        )
