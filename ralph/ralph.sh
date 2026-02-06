#!/usr/bin/env bash
set -euo pipefail

#===============================================================================
# Ralph - Autonomous Coding Loop
#===============================================================================
# External bash loop that runs Claude Code headlessly. Each iteration gets a
# fresh context window. Two-step workflow: /ralph-init → ralph.sh
#
# Usage: ralph.sh [options]
# Run ralph.sh --help for full documentation.
#===============================================================================

# Resolve script location and workspace
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_WORKSPACE="${RALPH_WORKSPACE:-$(dirname "$SCRIPT_PATH")}"
PROMPTS_DIR="$SCRIPT_PATH/prompts"
TEMPLATES_DIR="$SCRIPT_PATH/templates"

# Defaults
DEFAULT_MODEL="claude-opus-4-5"
DEFAULT_MAX=50

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#-------------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------------

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
    cat <<'EOF'
Ralph - Autonomous Coding Loop

USAGE:
    ralph.sh [options]               Run the loop (default command)
    ralph.sh run [options]           Same as above
    ralph.sh status                  Show current Ralph state
    ralph.sh cleanup                 Remove merged worktree branches

OPTIONS:
    -C <path>           Run in specified project directory
    --project <path>    Same as -C
    --model <model>     Model to use (default: claude-opus-4-5)
    --max <N>           Maximum iterations (default: 50)
    --worktree          Use git worktree isolation (off by default)
    --push              Push after each successful iteration
    --resume            Auto-resume existing worktree session
    --help, -h          Show this help message

WORKFLOW:
    1. Run /ralph-init in Claude Code (interactive interview)
    2. Run ralph.sh -C <project> in a separate terminal

EXAMPLES:
    ralph.sh -C projects/myapp               # Build in a subdirectory
    ralph.sh -C projects/myapp --max 20      # Limit to 20 iterations
    ralph.sh --worktree --push               # Use worktree + push
    ralph.sh status                          # Check current state
    ralph.sh cleanup                         # Clean up merged branches

ENVIRONMENT:
    RALPH_WORKSPACE     Path to workspace containing ralph/ directory
                        (default: parent of script directory)

EOF
    exit 0
}

# Get repo name from git
get_repo_name() {
    basename "$(git rev-parse --show-toplevel 2>/dev/null)" || echo "project"
}

# Get description for branch name from spec.md
get_branch_description() {
    if [[ -f "spec.md" ]]; then
        # Use first heading from spec.md
        head -5 spec.md | grep "^# " | head -1 | sed 's/^# //' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//' | cut -c1-30
    else
        echo "session"
    fi
}

# Generate timestamp for branch
get_timestamp() {
    date "+%Y%m%d-%H%M"
}

# Check for existing Ralph worktree/branch
find_existing_ralph_session() {
    git worktree list --porcelain 2>/dev/null | grep -A2 "^worktree" | grep "branch refs/heads/ralph/" | sed 's|.*refs/heads/||' | head -1 || true
}

# Get worktree path for a branch
get_worktree_path() {
    local branch="$1"
    git worktree list --porcelain 2>/dev/null | grep -B2 "branch refs/heads/$branch" | grep "^worktree" | sed 's/^worktree //' || true
}

# Append a line to progress.md's Iteration Log section
append_iteration_log() {
    local message="$1"
    local progress_file="progress.md"

    if [[ ! -f "$progress_file" ]]; then
        return
    fi

    # Append to the end of the file (Iteration Log is the last section)
    echo "$message" >> "$progress_file"
}

# Get last N lines from a string
last_lines() {
    echo "$1" | tail -n "${2:-20}"
}

#-------------------------------------------------------------------------------
# Status Command
#-------------------------------------------------------------------------------

cmd_status() {
    echo ""
    echo "=== Ralph Status ==="
    echo ""

    # Current branch
    local branch
    branch=$(git branch --show-current 2>/dev/null || echo "not a git repo")
    echo "Current branch: $branch"

    # Check for existing Ralph session
    local existing_session
    existing_session=$(find_existing_ralph_session)
    if [[ -n "$existing_session" ]]; then
        local worktree_path
        worktree_path=$(get_worktree_path "$existing_session")
        echo "Active Ralph session: $existing_session"
        echo "Worktree path: $worktree_path"
    else
        echo "Active Ralph session: none"
    fi

    # spec.md
    if [[ -f "spec.md" ]]; then
        local req_count
        req_count=$(grep -c "^\- \[ \]" spec.md 2>/dev/null || echo "0")
        log_success "spec.md: $req_count requirements"
    else
        log_warn "spec.md: missing (run /ralph-init first)"
    fi

    # progress.md
    if [[ -f "progress.md" ]]; then
        local total completed
        total=$(grep -c "^\- \[.\]" progress.md 2>/dev/null || echo "0")
        completed=$(grep -c "^\- \[x\]" progress.md 2>/dev/null || echo "0")
        log_success "progress.md: $completed/$total tasks completed"
    else
        log_warn "progress.md: missing"
    fi

    # AGENTS.md
    if [[ -f "AGENTS.md" ]]; then
        log_success "AGENTS.md: exists"
    else
        log_warn "AGENTS.md: missing"
    fi

    # Git status
    echo ""
    echo "Git working tree:"
    if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
        log_success "Clean"
    else
        log_warn "Has uncommitted changes"
    fi

    echo ""
}

#-------------------------------------------------------------------------------
# Cleanup Command
#-------------------------------------------------------------------------------

cmd_cleanup() {
    log_info "Looking for merged Ralph branches to clean up..."

    local main_branch
    main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

    # Find ralph/* branches that are merged
    local merged_branches
    merged_branches=$(git branch --merged "$main_branch" 2>/dev/null | grep "ralph/" | tr -d ' ' || true)

    if [[ -z "$merged_branches" ]]; then
        log_info "No merged Ralph branches found."
        return 0
    fi

    echo "Found merged branches:"
    echo "$merged_branches"
    echo ""

    read -rp "Remove these branches and their worktrees? (y/n) " confirm
    if [[ "$confirm" != "y" ]]; then
        log_info "Aborted."
        return 0
    fi

    for branch in $merged_branches; do
        local worktree_path
        worktree_path=$(get_worktree_path "$branch")

        if [[ -n "$worktree_path" ]]; then
            log_info "Removing worktree: $worktree_path"
            git worktree remove "$worktree_path" --force 2>/dev/null || true
        fi

        log_info "Deleting branch: $branch"
        git branch -d "$branch" 2>/dev/null || true
    done

    log_success "Cleanup complete."
}

#-------------------------------------------------------------------------------
# Main Loop
#-------------------------------------------------------------------------------

run_loop() {
    local max_iterations="$1"
    local model="$2"
    local use_worktree="$3"
    local auto_resume="$4"
    local do_push="$5"

    local prompt_file="$PROMPTS_DIR/PROMPT_loop.md"

    if [[ ! -f "$prompt_file" ]]; then
        log_error "Prompt file not found: $prompt_file"
        exit 1
    fi

    # Prerequisites check
    if [[ ! -f "spec.md" ]] || [[ ! -s "spec.md" ]]; then
        log_error "spec.md not found or empty. Run /ralph-init first."
        exit 1
    fi

    if [[ ! -f "progress.md" ]]; then
        log_warn "progress.md not found. Creating empty one."
        cat > "progress.md" <<'PROGRESSEOF'
# Progress

## Plan

[No plan yet — first iteration will analyze codebase and create task breakdown]

## Completed Work

[None yet]

## Failed Attempts

[None yet]

## Iteration Log

PROGRESSEOF
    fi

    if [[ ! -f "AGENTS.md" ]]; then
        log_warn "AGENTS.md not found. Claude won't know how to validate."
    fi

    # Store original directory
    local original_dir
    original_dir="$(pwd)"
    local repo_name
    repo_name=$(get_repo_name)
    local work_dir="$original_dir"
    local branch_name=""

    # Handle worktree if requested
    if [[ "$use_worktree" == "true" ]]; then
        local existing_session
        existing_session=$(find_existing_ralph_session)

        if [[ -n "$existing_session" ]]; then
            local existing_worktree
            existing_worktree=$(get_worktree_path "$existing_session")

            if [[ "$auto_resume" == "true" ]]; then
                log_info "Auto-resuming existing session: $existing_session"
                branch_name="$existing_session"
                work_dir="$existing_worktree"
            else
                echo ""
                log_warn "Found existing Ralph session on branch: $existing_session"
                log_warn "Worktree path: $existing_worktree"
                read -rp "Resume this session? (y/n) " resume_choice

                if [[ "$resume_choice" == "y" ]]; then
                    log_info "Resuming session..."
                    branch_name="$existing_session"
                    work_dir="$existing_worktree"
                else
                    log_info "Cleaning up existing session..."
                    git worktree remove "$existing_worktree" --force 2>/dev/null || true
                    git branch -D "$existing_session" 2>/dev/null || true
                    existing_session=""
                fi
            fi
        fi

        # Create new worktree if not resuming
        if [[ -z "$existing_session" ]] || [[ "$branch_name" == "" ]]; then
            local desc
            desc=$(get_branch_description)
            local timestamp
            timestamp=$(get_timestamp)
            branch_name="ralph/${desc}-${timestamp}"
            work_dir="../${repo_name}-ralph-${desc}-${timestamp}"

            log_info "Creating worktree: $work_dir"
            log_info "Branch: $branch_name"

            git worktree add "$work_dir" -b "$branch_name"
        fi

        cd "$work_dir"
        log_info "Working directory: $(pwd)"
    fi

    echo ""
    log_info "Starting Ralph"
    log_info "Model: $model"
    log_info "Max iterations: $max_iterations"
    log_info "Push: $do_push"
    log_info "Press Ctrl+C to stop"
    echo ""

    local iteration=0
    local completed=false
    local consecutive_errors=0

    while [[ $iteration -lt $max_iterations ]]; do
        iteration=$((iteration + 1))
        consecutive_errors_before=$consecutive_errors
        echo ""
        echo "════════════════════════════════════════════════════════════════════"
        echo "  ITERATION $iteration / $max_iterations"
        echo "════════════════════════════════════════════════════════════════════"
        echo ""

        # Record iteration start in progress.md
        append_iteration_log "- [$iteration] $(date '+%Y-%m-%d %H:%M:%S') — Started"

        # Get last commit hash before running Claude
        local commit_before
        commit_before=$(git rev-parse HEAD 2>/dev/null || echo "none")

        # Run Claude Code with prompt via stdin
        local output
        local exit_code
        set +e
        output=$(claude -p --dangerously-skip-permissions --model "$model" --verbose < "$prompt_file" 2>&1)
        exit_code=$?
        set -e

        echo "$output"

        # Get commit hash after running Claude
        local commit_after
        commit_after=$(git rev-parse HEAD 2>/dev/null || echo "none")

        # Update progress.md iteration log based on what happened
        if [[ $exit_code -ne 0 ]]; then
            consecutive_errors=$((consecutive_errors + 1))
            append_iteration_log "- [$iteration] $(date '+%Y-%m-%d %H:%M:%S') — ERROR exit code $exit_code"
            # Append last 20 lines of output for debugging
            append_iteration_log '```'
            append_iteration_log "$(last_lines "$output" 20)"
            append_iteration_log '```'
            log_error "Claude exited with code $exit_code (consecutive errors: $consecutive_errors)"
        elif [[ "$commit_before" != "$commit_after" ]]; then
            consecutive_errors=0
            local commit_msg
            commit_msg=$(git log -1 --format="%h %s" 2>/dev/null || echo "unknown")
            append_iteration_log "- [$iteration] $(date '+%Y-%m-%d %H:%M:%S') — Committed: $commit_msg"
            log_success "Committed: $commit_msg"

            # Push if requested
            if [[ "$do_push" == "true" ]]; then
                log_info "Pushing..."
                if [[ -n "$branch_name" ]]; then
                    git push origin "$branch_name" 2>/dev/null || git push -u origin "$branch_name"
                else
                    git push 2>/dev/null || true
                fi
            fi
        else
            consecutive_errors=0
            append_iteration_log "- [$iteration] $(date '+%Y-%m-%d %H:%M:%S') — No commit (task may have failed validation)"
        fi

        # Check for completion token
        if echo "$output" | grep -q "<promise>COMPLETE</promise>"; then
            log_success "Completion token detected!"
            completed=true
            break
        fi

        # Check for too many consecutive errors
        if [[ $consecutive_errors -ge 3 ]]; then
            log_error "3 consecutive errors — stopping. Check progress.md for details."
            break
        fi

        # Sleep between iterations
        if [[ $iteration -lt $max_iterations ]]; then
            log_info "Sleeping 2 seconds before next iteration..."
            sleep 2
        fi
    done

    echo ""
    echo "════════════════════════════════════════════════════════════════════"

    if [[ "$completed" == "true" ]]; then
        log_success "Ralph completed successfully after $iteration iterations!"
    else
        log_warn "Ralph stopped after $iteration iterations (max reached or error)"
    fi

    # Create draft PR if using worktree
    if [[ "$use_worktree" == "true" ]] && [[ -n "$branch_name" ]]; then
        echo ""
        log_info "Creating draft PR..."

        local main_branch
        main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

        local pr_title="[Ralph] $(head -5 spec.md | grep "^# " | head -1 | sed 's/^# //' || echo "session")"
        local total completed_count
        total=$(grep -c "^\- \[.\]" progress.md 2>/dev/null || echo "0")
        completed_count=$(grep -c "^\- \[x\]" progress.md 2>/dev/null || echo "0")

        if gh pr create --draft --title "$pr_title" --body "Automated PR created by Ralph.

## Session Info
- Branch: \`$branch_name\`
- Iterations: $iteration
- Status: $([ "$completed" == "true" ] && echo "Completed" || echo "Stopped")
- Tasks: $completed_count/$total completed

---
*Generated by Ralph*" --base "$main_branch" 2>/dev/null; then
            log_success "Draft PR created!"
        else
            log_warn "Could not create PR (may already exist or gh not configured)"
        fi

        echo ""
        log_info "Worktree remains at: $work_dir"
        log_info "Run 'ralph.sh cleanup' after merging to remove worktree"
    fi

    # Return to original directory
    cd "$original_dir"
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

main() {
    local command=""
    local max_iterations=""
    local model="$DEFAULT_MODEL"
    local use_worktree="false"
    local do_push="false"
    local auto_resume="false"
    local project_dir=""
    local positional_args=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                usage
                ;;
            -C|--project)
                project_dir="$2"
                shift 2
                ;;
            --model)
                model="$2"
                shift 2
                ;;
            --max)
                max_iterations="$2"
                shift 2
                ;;
            --worktree)
                use_worktree="true"
                shift
                ;;
            --push)
                do_push="true"
                shift
                ;;
            --resume)
                auto_resume="true"
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                echo "Run 'ralph.sh --help' for usage."
                exit 1
                ;;
            *)
                positional_args+=("$1")
                shift
                ;;
        esac
    done

    # Change to project directory if specified
    if [[ -n "$project_dir" ]]; then
        if [[ ! -d "$project_dir" ]]; then
            log_error "Project directory does not exist: $project_dir"
            exit 1
        fi
        log_info "Changing to project directory: $project_dir"
        cd "$project_dir"
    fi

    # Extract command from positional args (default: run)
    if [[ ${#positional_args[@]} -gt 0 ]]; then
        command="${positional_args[0]}"
    else
        command="run"
    fi

    # Handle commands
    case "$command" in
        run)
            max_iterations="${max_iterations:-$DEFAULT_MAX}"
            run_loop "$max_iterations" "$model" "$use_worktree" "$auto_resume" "$do_push"
            ;;
        status)
            cmd_status
            ;;
        cleanup)
            cmd_cleanup
            ;;
        *)
            log_error "Unknown command: $command"
            echo "Run 'ralph.sh --help' for usage."
            exit 1
            ;;
    esac
}

main "$@"
