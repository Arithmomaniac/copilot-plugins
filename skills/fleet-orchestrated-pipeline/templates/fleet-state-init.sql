-- Fleet Orchestrated Pipeline — SQL DDL
-- Run this to initialize fleet tracking tables in the session database.
-- These tables JOIN with the built-in todos/todo_deps tables.

CREATE TABLE IF NOT EXISTS fleet_pipeline (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Insert pipeline metadata:
-- INSERT INTO fleet_pipeline (key, value) VALUES
--   ('description', 'Refactor auth system'),
--   ('repo_root', 'C:\_SRC\ZTS'),
--   ('worktree_root', 'C:\_SRC\ZTS.worktrees\auth-refactor'),
--   ('current_layer', '0'),
--   ('layer_stage', 'worktrees_created');
-- Valid layer_stage values: worktrees_created, implementing, implemented,
--   reviewing, reviewed, auto_applying, auto_applied, manual_reviewing, prs_created

CREATE TABLE IF NOT EXISTS fleet_tasks (
    id TEXT PRIMARY KEY,       -- same id as in todos table
    layer INTEGER NOT NULL,
    worktree_slug TEXT,        -- e.g. t3-jwt-provider
    branch_name TEXT,          -- e.g. feature/avilevin/auth-refactor/t3-jwt-provider
    base_branch TEXT,          -- origin/main or parent task's branch
    pr_url TEXT,
    work_item_id TEXT,
    deferred_reason TEXT
);

CREATE TABLE IF NOT EXISTS fleet_subtasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    description TEXT NOT NULL,
    done INTEGER DEFAULT 0,   -- 0 or 1
    FOREIGN KEY (task_id) REFERENCES fleet_tasks(id)
);

CREATE TABLE IF NOT EXISTS fleet_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    model TEXT NOT NULL,
    severity TEXT,             -- CRITICAL, IMPORTANT, MINOR
    finding TEXT NOT NULL,
    status TEXT DEFAULT 'open', -- open, auto_applied, flagged, dismissed, timeout
    FOREIGN KEY (task_id) REFERENCES fleet_tasks(id)
);
