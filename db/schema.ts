import { index, integer, sqliteTable, text } from 'drizzle-orm/sqlite-core';

export const projects = sqliteTable('projects', {
  id: text('id').primaryKey(),
  ownerId: text('owner_id').notNull(),
  processorProjectId: text('processor_project_id'),
  title: text('title').notNull(),
  sourceName: text('source_name'),
  stage: text('stage').notNull().default('pending'),
  progress: integer('progress').notNull().default(0),
  message: text('message').notNull().default('Aguardando processamento'),
  createdAt: integer('created_at', { mode: 'timestamp_ms' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp_ms' }).notNull(),
}, (table) => [
  index('idx_projects_owner_created').on(table.ownerId, table.createdAt),
  index('idx_projects_stage').on(table.stage),
]);

export const clips = sqliteTable('clips', {
  id: text('id').primaryKey(),
  projectId: text('project_id').notNull().references(() => projects.id, { onDelete: 'cascade' }),
  title: text('title').notNull(),
  startMs: integer('start_ms').notNull(),
  endMs: integer('end_ms').notNull(),
  qualityScore: integer('quality_score').notNull(),
  outputKey: text('output_key'),
  createdAt: integer('created_at', { mode: 'timestamp_ms' }).notNull(),
}, (table) => [index('idx_clips_project_score').on(table.projectId, table.qualityScore)]);
