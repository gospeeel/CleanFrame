ALTER TYPE "AnalysisStatus" ADD VALUE IF NOT EXISTS 'CANCELLED';

CREATE TYPE "NotificationType" AS ENUM (
  'ANALYSIS_DONE',
  'ANALYSIS_FAILED',
  'ANALYSIS_LONG_RUNNING',
  'ANALYSIS_CANCELLED'
);

ALTER TABLE "analyses"
  ADD COLUMN "error_code" VARCHAR(64),
  ADD COLUMN "source_file_path" VARCHAR(1024),
  ADD COLUMN "queue_job_id" VARCHAR(128),
  ADD COLUMN "queued_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN "started_at" TIMESTAMP(3),
  ADD COLUMN "attempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "worker_id" VARCHAR(128);

CREATE INDEX "analyses_queue_job_id_idx" ON "analyses"("queue_job_id");

CREATE TABLE "notifications" (
  "id" UUID NOT NULL,
  "user_id" UUID NOT NULL,
  "type" "NotificationType" NOT NULL,
  "title" VARCHAR(160) NOT NULL,
  "message" VARCHAR(512) NOT NULL,
  "analysis_id" UUID,
  "read_at" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "notifications_user_id_read_at_created_at_idx"
  ON "notifications"("user_id", "read_at", "created_at");

CREATE INDEX "notifications_analysis_id_idx" ON "notifications"("analysis_id");

ALTER TABLE "notifications"
  ADD CONSTRAINT "notifications_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "notifications"
  ADD CONSTRAINT "notifications_analysis_id_fkey"
  FOREIGN KEY ("analysis_id") REFERENCES "analyses"("id") ON DELETE SET NULL ON UPDATE CASCADE;
