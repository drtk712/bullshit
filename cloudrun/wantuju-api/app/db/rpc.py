"""Names of the plpgsql functions exposed through PostgREST RPC."""

RPC_FUNCTIONS = frozenset(
    {
        "wantuju_create_pending_job",
        "wantuju_consume_existing_job",
        "wantuju_refund_failed_job",
        "wantuju_claim_job",
        "wantuju_adjust_points",
        "wantuju_delete_user",
        "wantuju_ensure_user",
        "wantuju_claim_share",
        "wantuju_check_in",
        "wantuju_patch_document",
    }
)
