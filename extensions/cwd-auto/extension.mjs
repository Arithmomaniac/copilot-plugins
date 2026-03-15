// Extension: cwd-auto
// Detects when a user's prompt implies working in a different directory
// and offers Always/Never session-scoped permission to auto-switch via /cwd.

import { approveAll } from "@github/copilot-sdk";
import { joinSession } from "@github/copilot-sdk/extension";
import { normalize } from "node:path";

// ── Repository Index ──────────────────────────────────────────────────
// Maps friendly names to absolute directory paths.
// Sourced from the user's custom instructions Repository Index table.
const REPO_INDEX = [
    { names: ["zts", "zts root", "work repo"],                                       path: "C:\\_SRC\\ZTS" },
    { names: ["zts teamdocs", "team docs"],                                           path: "C:\\_SRC\\ZTS-TeamDocs" },
    { names: ["tallyai", "tally", "tally root"],                                      path: "C:\\_SRC\\tallyai" },
    { names: ["budget labeler", "levin budget labeler", "caspion"],                    path: "C:\\_SRC\\tallyai\\levin_budget_labeler" },
    { names: ["copilot session tools", "session tools", "session store repo"],          path: "C:\\_SRC\\copilot-repository-tools" },
    { names: ["fleet orchestrator"],                                                   path: "C:\\_SRC\\fleet-orchestrator" },
    { names: ["pastebin", "avilevin pastebin"],                                        path: "C:\\_SRC\\avilevin-pastebin" },
    { names: ["copilot plugins", "copilot-plugins"],                                   path: "C:\\_SRC\\copilot-plugins" },
    { names: ["html agility pack", "hap"],                                             path: "C:\\_SRC\\html-agility-pack" },
    { names: ["library helper", "library org il"],                                     path: "C:\\_SRC\\library_org_il_helper" },
    { names: ["playwright insurance", "insurance claims"],                              path: "C:\\_SRC\\playwright_insurance_claims" },
    { names: ["copilot ui"],                                                           path: "C:\\_SRC\\copilot-ui\\copilot-ui" },
    { names: ["tmax"],                                                                 path: "C:\\_SRC\\tmax" },
];

// Flatten and sort longest-first for greedy matching
const SORTED_ENTRIES = REPO_INDEX.flatMap((repo) =>
    repo.names.map((name) => ({ name, path: repo.path })),
).sort((a, b) => b.name.length - a.name.length);

// ── Session State ─────────────────────────────────────────────────────
// Permissions are session-scoped (lost on /clear or CLI exit).
const permissions = new Map(); // norm(path) → "always" | "never"

function norm(p) {
    return normalize(p).toLowerCase();
}

// ── Detection ─────────────────────────────────────────────────────────
function detectDirectoryReference(prompt, currentCwd) {
    const normalizedCwd = norm(currentCwd);

    for (const entry of SORTED_ENTRIES) {
        const escaped = entry.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const pattern = new RegExp(`\\b${escaped}\\b`, "i");
        if (pattern.test(prompt)) {
            const normalizedTarget = norm(entry.path);
            // Skip if already in target directory or a subdirectory of it
            if (
                normalizedCwd === normalizedTarget ||
                normalizedCwd.startsWith(normalizedTarget + "\\")
            ) {
                return null;
            }
            return { targetPath: entry.path, matchedName: entry.name };
        }
    }
    return null;
}

// ── Extension ─────────────────────────────────────────────────────────
const session = await joinSession({
    onPermissionRequest: approveAll,
    hooks: {
        onUserPromptSubmitted: async (input) => {
            // Skip slash commands (including our own /cwd injections)
            if (input.prompt.trim().startsWith("/")) return;

            const match = detectDirectoryReference(input.prompt, input.cwd);
            if (!match) return;

            const { targetPath, matchedName } = match;
            const perm = permissions.get(norm(targetPath));

            if (perm === "always") {
                await session.log(`cwd-auto → ${matchedName}`, { ephemeral: true });
                setTimeout(
                    () => session.send({ prompt: `/cwd ${targetPath}` }),
                    0,
                );
                return {
                    additionalContext: `[cwd-auto] Auto-switching to ${targetPath} (${matchedName}) per standing permission. /cwd executes after this turn — use absolute paths under ${targetPath} for file operations this turn.`,
                };
            }

            if (perm === "never") {
                return; // Silently skip — user declined this session
            }

            // First encounter — instruct the agent to ask
            return {
                additionalContext: [
                    `[cwd-auto] The user's request mentions "${matchedName}" (${targetPath}), but the current directory is ${input.cwd}.`,
                    `Before proceeding, use the ask_user tool to ask whether to change the working directory.`,
                    `Present exactly two choices: "Always" (auto-switch to this directory for the rest of the session without asking) and "Never" (don't switch, don't ask again this session).`,
                    `After receiving the answer, call the cwd_auto_record tool with directory="${targetPath}" and the user's choice.`,
                    `Then proceed with the user's original request.`,
                ].join(" "),
            };
        },
    },
    tools: [
        {
            name: "cwd_auto_record",
            description:
                "Record the user's Always/Never permission for auto-switching to a directory. If 'always', triggers /cwd to change the working directory.",
            parameters: {
                type: "object",
                properties: {
                    directory: {
                        type: "string",
                        description: "Absolute path of the target directory",
                    },
                    permission: {
                        type: "string",
                        enum: ["always", "never"],
                        description: "The user's choice",
                    },
                },
                required: ["directory", "permission"],
            },
            handler: async (args) => {
                permissions.set(norm(args.directory), args.permission);
                if (args.permission === "always") {
                    await session.log(
                        `cwd-auto: ALWAYS → ${args.directory}`,
                        { ephemeral: true },
                    );
                    setTimeout(
                        () =>
                            session.send({
                                prompt: `/cwd ${args.directory}`,
                            }),
                        0,
                    );
                    return `Recorded ALWAYS for ${args.directory}. Switching now via /cwd.`;
                }
                await session.log(`cwd-auto: NEVER → ${args.directory}`, {
                    ephemeral: true,
                });
                return `Recorded NEVER for ${args.directory}. Won't ask again this session.`;
            },
        },
        {
            name: "cwd_auto_status",
            description:
                "Show or reset cwd-auto directory permissions for this session. Call with no args to list, or pass reset='all' or reset='<path>' to clear.",
            parameters: {
                type: "object",
                properties: {
                    reset: {
                        type: "string",
                        description:
                            "Optional: directory path to reset, or 'all' to reset everything",
                    },
                },
            },
            handler: async (args) => {
                if (args?.reset) {
                    if (args.reset === "all") {
                        permissions.clear();
                        return "All cwd-auto permissions reset.";
                    }
                    const key = norm(args.reset);
                    if (permissions.has(key)) {
                        permissions.delete(key);
                        return `Permission reset for ${args.reset}.`;
                    }
                    return `No permission found for ${args.reset}.`;
                }
                if (permissions.size === 0) {
                    return "No directory permissions recorded this session.";
                }
                return [...permissions.entries()]
                    .map(([dir, perm]) => `${perm.toUpperCase()}: ${dir}`)
                    .join("\n");
            },
        },
    ],
});

await session.log("cwd-auto extension loaded");
