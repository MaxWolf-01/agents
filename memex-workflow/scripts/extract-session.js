#!/usr/bin/env node

/**
 * Extract session transcript from Claude Code session files.
 *
 * Adapted from Armin Ronacher's agent-stuff repo.
 * Modified to require explicit session name for parallel session safety.
 *
 * Usage:
 *   ./extract-session.js --name <session-name> [--cwd /path/to/dir]
 *   ./extract-session.js <session-path>  # direct path to .jsonl file
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Parse arguments
const args = process.argv.slice(2);
let sessionPath = null;
let sessionName = null;
let cwd = process.cwd();
let maxMessages = 0; // 0 = unlimited

for (let i = 0; i < args.length; i++) {
  if ((args[i] === '--name' || args[i] === '-n') && args[i + 1]) {
    sessionName = args[++i];
  } else if (args[i] === '--cwd' && args[i + 1]) {
    cwd = args[++i];
  } else if (args[i] === '--max-messages' && args[i + 1]) {
    maxMessages = parseInt(args[++i], 10);
  } else if (!args[i].startsWith('-')) {
    sessionPath = args[i];
  }
}

/**
 * Encode CWD for session path lookup (Claude Code style)
 */
function encodeCwd(cwd) {
  return cwd.replace(/\//g, '-');
}

/**
 * Find session by custom title (name)
 * Searches all .jsonl files for a matching customTitle entry
 */
function findSessionByName(dir, name) {
  if (!fs.existsSync(dir)) {
    return null;
  }

  const files = fs.readdirSync(dir)
    .filter(f => f.endsWith('.jsonl'))
    .map(f => path.join(dir, f));

  for (const filePath of files) {
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.trim().split('\n');

      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          if (entry.type === 'custom-title' && entry.customTitle === name) {
            return filePath;
          }
        } catch (e) {
          // Skip invalid lines
        }
      }
    } catch (e) {
      // Skip unreadable files
    }
  }

  return null;
}

/**
 * Parse Claude Code session format
 */
function parseClaudeSession(content) {
  const messages = [];
  const lines = content.trim().split('\n');

  for (const line of lines) {
    try {
      const entry = JSON.parse(line);
      if (entry.type === 'user' || entry.type === 'assistant') {
        if (entry.message?.role && entry.message?.content) {
          messages.push({
            role: entry.message.role,
            content: extractContent(entry.message.content),
            timestamp: entry.timestamp
          });
        }
      }
    } catch (e) {
      // Skip invalid lines
    }
  }

  return messages;
}

/**
 * Extract text content from various content formats
 */
function extractContent(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return JSON.stringify(content);

  const parts = [];
  for (const item of content) {
    if (typeof item === 'string') {
      parts.push(item);
    } else if (item.type === 'text') {
      parts.push(item.text);
    } else if (item.type === 'input_text') {
      parts.push(item.text);
    } else if (item.type === 'tool_use') {
      parts.push(`[Tool: ${item.name}]\n${JSON.stringify(item.input, null, 2)}`);
    } else if (item.type === 'tool_result') {
      const result = typeof item.content === 'string'
        ? item.content
        : JSON.stringify(item.content);
      // Truncate long tool results
      const truncated = result.length > 500
        ? result.slice(0, 500) + '\n[... truncated ...]'
        : result;
      parts.push(`[Tool Result]\n${truncated}`);
    } else {
      parts.push(`[${item.type}]`);
    }
  }

  return parts.join('\n');
}

/**
 * Format messages as readable transcript
 */
function formatTranscript(messages, maxMessages = 0) {
  // 0 = unlimited
  const recent = maxMessages > 0 ? messages.slice(-maxMessages) : messages;
  const lines = [];

  for (const msg of recent) {
    const role = msg.role.toUpperCase();
    lines.push(`\n### ${role}:\n`);
    lines.push(msg.content);
  }

  if (maxMessages > 0 && messages.length > maxMessages) {
    lines.unshift(`\n[... ${messages.length - maxMessages} earlier messages omitted ...]\n`);
  }

  return lines.join('\n');
}

// Main
async function main() {
  let targetPath;

  if (sessionPath) {
    // Explicit path provided
    if (!fs.existsSync(sessionPath)) {
      console.error(`Error: Session file not found: ${sessionPath}`);
      process.exit(1);
    }
    targetPath = sessionPath;
  } else if (sessionName) {
    // Search by session name
    const projectDir = path.join(os.homedir(), '.claude', 'projects', encodeCwd(cwd));

    if (!fs.existsSync(projectDir)) {
      console.error(`Error: No Claude Code sessions found for: ${cwd}`);
      process.exit(1);
    }

    targetPath = findSessionByName(projectDir, sessionName);

    if (!targetPath) {
      console.error(`Error: No session named '${sessionName}' found.`);
      console.error(`Use /rename to name your session first.`);
      console.error(`\nSearched in: ${projectDir}`);
      process.exit(1);
    }
  } else {
    // No name or path provided
    console.error(`Error: Session name required for parallel session safety.`);
    console.error(`\nUsage:`);
    console.error(`  extract-session.js --name <session-name>`);
    console.error(`  extract-session.js <path-to-session.jsonl>`);
    console.error(`\nName your session with /rename first, then pass that name here.`);
    process.exit(1);
  }

  // Read and parse session
  const content = fs.readFileSync(targetPath, 'utf8');
  const messages = parseClaudeSession(content);

  // Output metadata and transcript
  console.log(`# Session Transcript`);
  console.log(`File: ${targetPath}`);
  console.log(`Messages: ${messages.length}`);
  console.log('');
  console.log(formatTranscript(messages, maxMessages));
}

main().catch(e => {
  console.error(e.message);
  process.exit(1);
});
