from dataclasses import dataclass


@dataclass
class SafetyContext:
    apply: bool
    dry_run: bool


def resolve_mode(apply_flag: bool, dry_run_flag: bool) -> SafetyContext:
    if apply_flag and dry_run_flag:
        raise ValueError("Choose either --apply or --dry-run, not both.")
    if apply_flag:
        return SafetyContext(apply=True, dry_run=False)
    return SafetyContext(apply=False, dry_run=True)


def confirm_apply(action_label: str) -> bool:
    prompt = f"Type APPLY to confirm: {action_label}\n> "
    reply = input(prompt).strip()
    return reply == "APPLY"


def allow_action(context: SafetyContext, action_label: str) -> bool:
    if context.dry_run:
        return False
    return confirm_apply(action_label)
