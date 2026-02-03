"""ZERG CLI commands."""

from zerg.commands.analyze import analyze
from zerg.commands.build import build
from zerg.commands.cleanup import cleanup
from zerg.commands.debug import debug
from zerg.commands.design import design
from zerg.commands.document import document
from zerg.commands.git_cmd import git_cmd
from zerg.commands.init import init
from zerg.commands.install_commands import install_commands, uninstall_commands
from zerg.commands.logs import logs
from zerg.commands.merge_cmd import merge_cmd
from zerg.commands.plan import plan
from zerg.commands.refactor import refactor
from zerg.commands.retry import retry
from zerg.commands.review import review
from zerg.commands.rush import rush
from zerg.commands.security_rules_cmd import security_rules_group
from zerg.commands.status import status
from zerg.commands.stop import stop
from zerg.commands.test_cmd import test_cmd
from zerg.commands.wiki import wiki

__all__ = [
    "analyze",
    "build",
    "cleanup",
    "design",
    "git_cmd",
    "init",
    "logs",
    "merge_cmd",
    "plan",
    "refactor",
    "retry",
    "review",
    "rush",
    "security_rules_group",
    "status",
    "stop",
    "test_cmd",
    "debug",
    "document",
    "install_commands",
    "uninstall_commands",
    "wiki",
]
