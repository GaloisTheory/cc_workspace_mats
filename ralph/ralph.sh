#!/usr/bin/env bash
set -euo pipefail

#===============================================================================
# Ralph - Autonomous Coding Loop
#===============================================================================
# External bash loop that runs Claude Code headlessly. Each iteration gets a
# fresh context window - this is the core advantage over plugin approaches.
#
# Usage: ralph.sh <mode> [options]
# Run ralph.sh --help for full documentation.
#===============================================================================

# Resolve script location and workspace
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_WORKSPACE="${RALPH_WORKSPACE:-$(dirname "$SCRIPT_PATH")}"
PROMPTS_DIR="$SCRIPT_PATH/prompts"
TEMPLATES_DIR="$SCRIPT_PATH/templates"

# Defaults
DEFAULT_MODEL="claude-opus-4-5"
DEFAULT_PLAN_MAX=5
DEFAULT_BUILD_MAX=50
DEFAULT_PLANWORK_MAX=10

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
    ralph.sh <command> [options]
    ralph.sh -C <project-path> <command> [options]

COMMANDS:
    init                    Set up Ralph files in current project
    plan [max]              Planning mode - generate IMPLEMENTATION_PLAN.md
    build [max]             Building mode - implement tasks from plan
    plan-work "desc" [max]  Scoped planning for a work branch
    status                  Show current Ralph state
    cleanup                 Remove merged worktree branches

OPTIONS:
    -C <path>           Run in specified project directory
    --project <path>    Same as -C
    --model <model>     Model to use (default: claude-opus-4-5-20250514)
    --max <N>           Maximum iterations (default: 5 for plan, 50 for build)
    --no-worktree       Skip worktree creation, work on current branch
    --resume            Auto-resume existing session without prompting
    --help, -h          Show this help message

EXAMPLES:
    ralph.sh init                        # Initialize Ralph in current project
    ralph.sh plan                        # Generate implementation plan
    ralph.sh build --max 30              # Build with up to 30 iterations
    ralph.sh plan-work "add auth" --max 20
    ralph.sh status                      # Check current state
    ralph.sh cleanup                     # Clean up merged branches
    ralph.sh -C projects/myapp build     # Build in a subdirectory project

ENVIRONMENT:
    RALPH_WORKSPACE     Path to workspace containing ralph/ directory
                        (default: parent of script directory)

WORKFLOW:
    1. Run /ralph-init in Claude Code (or ralph.sh init)
    2. Run /ralph-specs to generate specifications interactively
    3. Run /ralph-launch to verify everything is ready
    4. Run ralph.sh plan (in separate terminal) to generate plan
    5. Run ralph.sh build (in separate terminal) to implement

EOF
    exit 0
}

# Get repo name from git
get_repo_name() {
    basename "$(git rev-parse --show-toplevel 2>/dev/null)" || echo "project"
}

# Get description for branch name
get_branch_description() {
    local mode="$1"
    local explicit_desc="${2:-}"

    if [[ -n "$explicit_desc" ]]; then
        # Sanitize description for branch name
        echo "$explicit_desc" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//'
    elif [[ -d "specs" ]] && [[ -n "$(ls -A specs 2>/dev/null)" ]]; then
        # Use first spec filename (without extension)
        basename "$(ls specs/* 2>/dev/null | head -1)" | sed 's/\.[^.]*$//' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g'
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
    # Look for existing ralph/* branches with worktrees
    git worktree list --porcelain 2>/dev/null | grep -A2 "^worktree" | grep "branch refs/heads/ralph/" | sed 's|.*refs/heads/||' | head -1 || true
}

# Get worktree path for a branch
get_worktree_path() {
    local branch="$1"
    git worktree list --porcelain 2>/dev/null | grep -B2 "branch refs/heads/$branch" | grep "^worktree" | sed 's/^worktree //' || true
}

# Count completed vs total tasks in IMPLEMENTATION_PLAN.md
count_tasks() {
    local plan_file="${1:-IMPLEMENTATION_PLAN.md}"
    if [[ -f "$plan_file" ]]; then
        local total completed
        total=$(grep -c "^### Task" "$plan_file" 2>/dev/null || echo "0")
        completed=$(grep -c '\[x\].*Incomplete\|\*\*Status\*\*:.*\[x\]' "$plan_file" 2>/dev/null || echo "0")
        # Alternative pattern for completed tasks
        if [[ "$completed" -eq 0 ]]; then
            completed=$(grep -c "- \*\*Status\*\*: \[x\]" "$plan_file" 2>/dev/null || echo "0")
        fi
        echo "$completed/$total"
    else
        echo "0/0"
    fi
}

#-------------------------------------------------------------------------------
# Init Command
#-------------------------------------------------------------------------------

cmd_init() {
    log_info "Initializing Ralph in current project..."

    local created=()
    local skipped=()

    # Create specs directory
    if [[ ! -d "specs" ]]; then
        mkdir -p specs
        created+=("specs/")
    else
        skipped+=("specs/ (already exists)")
    fi

    # Copy AGENTS.md template
    if [[ ! -f "AGENTS.md" ]]; then
        if [[ -f "$TEMPLATES_DIR/AGENTS.md.template" ]]; then
            cp "$TEMPLATES_DIR/AGENTS.md.template" "AGENTS.md"
            created+=("AGENTS.md")
        else
            log_warn "AGENTS.md.template not found in $TEMPLATES_DIR"
        fi
    else
        skipped+=("AGENTS.md (already exists)")
    fi

    # Create empty IMPLEMENTATION_PLAN.md
    if [[ ! -f "IMPLEMENTATION_PLAN.md" ]]; then
        cat > "IMPLEMENTATION_PLAN.md" <<'PLANEOF'
# Implementation Plan

> Generated by Ralph. Do not edit manually during active sessions.

## Overview

[Plan not yet generated. Run `ralph.sh plan` to generate.]

## Tasks

[No tasks yet]
PLANEOF
        created+=("IMPLEMENTATION_PLAN.md")
    else
        skipped+=("IMPLEMENTATION_PLAN.md (already exists)")
    fi

    # Summary
    echo ""
    if [[ ${#created[@]} -gt 0 ]]; then
        log_success "Created:"
        for item in "${created[@]}"; do
            echo "  - $item"
        done
    fi

    if [[ ${#skipped[@]} -gt 0 ]]; then
        log_warn "Skipped (already exist):"
        for item in "${skipped[@]}"; do
            echo "  - $item"
        done
    fi

    echo ""
    log_info "Next steps:"
    echo "  1. Edit AGENTS.md to configure validation commands"
    echo "  2. Create spec files in specs/"
    echo "  3. Run ralph.sh plan to generate implementation plan"
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

    # AGENTS.md
    if [[ -f "AGENTS.md" ]]; then
        log_success "AGENTS.md: exists"
    else
        log_warn "AGENTS.md: missing"
    fi

    # specs/
    if [[ -d "specs" ]]; then
        local spec_count
        spec_count=$(ls -1 specs/*.md 2>/dev/null | wc -l | tr -d ' ')
        log_success "specs/: $spec_count spec file(s)"
    else
        log_warn "specs/: missing"
    fi

    # IMPLEMENTATION_PLAN.md
    if [[ -f "IMPLEMENTATION_PLAN.md" ]]; then
        local task_progress
        task_progress=$(count_tasks "IMPLEMENTATION_PLAN.md")
        log_success "IMPLEMENTATION_PLAN.md: $task_progress tasks completed"
    else
        log_warn "IMPLEMENTATION_PLAN.md: missing"
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
# Main Loop (plan/build/plan-work)
#-------------------------------------------------------------------------------

run_loop() {
    local mode="$1"
    local description="${2:-}"
    local max_iterations="$3"
    local model="$4"
    local use_worktree="$5"
    local auto_resume="$6"

    # Determine prompt file
    local prompt_file
    case "$mode" in
        plan)
            prompt_file="$PROMPTS_DIR/PROMPT_plan.md"
            ;;
        build)
            prompt_file="$PROMPTS_DIR/PROMPT_build.md"
            ;;
        plan-work)
            prompt_file="$PROMPTS_DIR/PROMPT_plan_work.md"
            ;;
    esac

    if [[ ! -f "$prompt_file" ]]; then
        log_error "Prompt file not found: $prompt_file"
        exit 1
    fi

    # Verify prerequisites
    if [[ ! -f "AGENTS.md" ]]; then
        log_error "AGENTS.md not found. Run 'ralph.sh init' first."
        exit 1
    fi

    if [[ ! -d "specs" ]] || [[ -z "$(ls -A specs 2>/dev/null)" ]]; then
        log_error "specs/ directory is empty or missing. Create spec files first."
        exit 1
    fi

    if [[ "$mode" == "build" ]] && [[ ! -f "IMPLEMENTATION_PLAN.md" ]]; then
        log_error "IMPLEMENTATION_PLAN.md not found. Run 'ralph.sh plan' first."
        exit 1
    fi

    # Store original directory
    local original_dir
    original_dir="$(pwd)"
    local repo_name
    repo_name=$(get_repo_name)
    local work_dir="$original_dir"
    local branch_name=""

    # Handle worktree for build and plan-work modes
    if [[ "$use_worktree" == "true" ]] && [[ "$mode" != "plan" ]]; then
        # Check for existing session
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
            desc=$(get_branch_description "$mode" "$description")
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
    log_info "Starting Ralph in $mode mode"
    log_info "Model: $model"
    log_info "Max iterations: $max_iterations"
    log_info "Press Ctrl+C to stop"
    echo ""

    local iteration=0
    local completed=false

    while [[ $iteration -lt $max_iterations ]]; do
        iteration=$((iteration + 1))
        echo ""
        echo "════════════════════════════════════════════════════════════════════"
        echo "  ITERATION $iteration / $max_iterations"
        echo "════════════════════════════════════════════════════════════════════"
        echo ""

        # Run Claude Code with prompt via stdin
        # For plan-work mode, substitute ${WORK_SCOPE} using envsubst
        local output
        set +e
        if [[ "$mode" == "plan-work" ]]; then
            export WORK_SCOPE="$description"
            output=$(envsubst '${WORK_SCOPE}' < "$prompt_file" | claude -p --dangerously-skip-permissions --model "$model" --verbose 2>&1)
        else
            output=$(claude -p --dangerously-skip-permissions --model "$model" --verbose < "$prompt_file" 2>&1)
        fi
        local exit_code=$?
        set -e

        echo "$output"

        if [[ $exit_code -ne 0 ]]; then
            log_error "Claude Code exited with code $exit_code"
            break
        fi

        # Push changes after each iteration (if using worktree)
        if [[ "$use_worktree" == "true" ]] && [[ -n "$branch_name" ]]; then
            log_info "Pushing changes to origin..."
            git push origin "$branch_name" 2>/dev/null || git push -u origin "$branch_name"
        fi

        # Check for completion token
        if echo "$output" | grep -q "<promise>COMPLETE</promise>"; then
            log_success "Completion token detected!"
            completed=true
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

        # Get main branch for PR base
        local main_branch
        main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

        # Create draft PR
        local pr_title="[Ralph] ${description:-$mode session}"
        if gh pr create --draft --title "$pr_title" --body "Automated PR created by Ralph ($mode mode)

## Session Info
- Branch: \`$branch_name\`
- Iterations: $iteration
- Status: $([ "$completed" == "true" ] && echo "Completed" || echo "Stopped")

## Tasks
$(count_tasks IMPLEMENTATION_PLAN.md) tasks completed

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
    local description=""
    local max_iterations=""
    local model="$DEFAULT_MODEL"
    local use_worktree="true"
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
            --no-worktree)
                use_worktree="false"
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

    # Extract command and arguments from positional args
    if [[ ${#positional_args[@]} -gt 0 ]]; then
        command="${positional_args[0]}"
    fi

    # Handle commands
    case "$command" in
        "")
            usage
            ;;
        init)
            cmd_init
            ;;
        status)
            cmd_status
            ;;
        cleanup)
            cmd_cleanup
            ;;
        plan)
            max_iterations="${max_iterations:-${positional_args[1]:-$DEFAULT_PLAN_MAX}}"
            run_loop "plan" "" "$max_iterations" "$model" "false" "$auto_resume"
            ;;
        build)
            max_iterations="${max_iterations:-${positional_args[1]:-$DEFAULT_BUILD_MAX}}"
            run_loop "build" "" "$max_iterations" "$model" "$use_worktree" "$auto_resume"
            ;;
        plan-work)
            if [[ ${#positional_args[@]} -lt 2 ]]; then
                log_error "plan-work requires a description"
                echo "Usage: ralph.sh plan-work \"description\" [max]"
                exit 1
            fi
            description="${positional_args[1]}"
            max_iterations="${max_iterations:-${positional_args[2]:-$DEFAULT_PLANWORK_MAX}}"
            run_loop "plan-work" "$description" "$max_iterations" "$model" "$use_worktree" "$auto_resume"
            ;;
        *)
            log_error "Unknown command: $command"
            echo "Run 'ralph.sh --help' for usage."
            exit 1
            ;;
    esac
}

main "$@"
