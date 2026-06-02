CREATE TABLE IF NOT EXISTS "audit_events" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "action" VARCHAR(80) NOT NULL,
  "user_id" UUID,
  "analysis_id" UUID,
  "metadata" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "audit_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "audit_events_action_created_at_idx" ON "audit_events"("action", "created_at");
CREATE INDEX IF NOT EXISTS "audit_events_user_id_created_at_idx" ON "audit_events"("user_id", "created_at");
CREATE INDEX IF NOT EXISTS "audit_events_analysis_id_idx" ON "audit_events"("analysis_id");

ALTER TABLE "audit_events"
  ADD CONSTRAINT "audit_events_analysis_id_fkey"
  FOREIGN KEY ("analysis_id") REFERENCES "analyses"("id") ON DELETE SET NULL ON UPDATE CASCADE;
