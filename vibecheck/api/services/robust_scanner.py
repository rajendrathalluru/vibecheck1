import traceback
from datetime import datetime, timezone

from sqlalchemy import func, select

from api.agents import AGENT_MAP
from api.agents.http_tools import http_request
from api.models.assessment import Assessment
from api.models.finding import Finding


async def run_robust_scan(
    assessment_id: str,
    target_url: str,
    agent_names: list[str],
    depth: str,
    db_factory,
):
    """
    Main robust scan orchestrator. Runs as a FastAPI BackgroundTask.
    Creates its own DB session since background tasks outlive the request.
    """
    async with db_factory() as db:
        assessment = await db.get(Assessment, assessment_id)
        if not assessment:
            return

        try:
            assessment.status = "scanning"
            await db.commit()

            health_check = await http_request(target_url, "GET", "/")
            if "error" in health_check and health_check["error"] == "connection_failed":
                assessment.status = "failed"
                assessment.error_type = "TARGET_UNREACHABLE"
                assessment.error_message = (
                    f"Cannot reach {target_url}: {health_check.get('message', 'connection failed')}"
                )[:500]
                await db.commit()
                return

            for agent_name in agent_names:
                agent_class = AGENT_MAP.get(agent_name)
                if not agent_class:
                    continue

                try:
                    agent = agent_class(
                        assessment_id=assessment_id,
                        target_url=target_url,
                        depth=depth,
                        db_session=db,
                    )
                    await agent.run()
                    await db.commit()
                except Exception as e:
                    print(f"[robust_scanner] Agent '{agent_name}' failed: {e}")
                    traceback.print_exc()
                    await db.rollback()
                    continue

            count_query = (
                select(Finding.severity, func.count(Finding.id))
                .where(Finding.assessment_id == assessment_id)
                .group_by(Finding.severity)
            )
            result = await db.execute(count_query)
            severity_counts = dict(result.all())

            finding_counts = {
                "critical": severity_counts.get("critical", 0),
                "high": severity_counts.get("high", 0),
                "medium": severity_counts.get("medium", 0),
                "low": severity_counts.get("low", 0),
                "info": severity_counts.get("info", 0),
            }
            finding_counts["total"] = sum(finding_counts.values())

            assessment.finding_counts = finding_counts
            assessment.status = "complete"
            assessment.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            assessment.status = "failed"
            assessment.error_type = "SCAN_ERROR"
            assessment.error_message = str(e)[:500]
            await db.commit()
