from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse
import logging
import re

if TYPE_CHECKING:
    from git import Repo
    from github.Repository import Repository

__all__ = ('convert_git_ssh_url_to_https', 'get_github_default_branch',
           'merge_dependabot_pull_requests')

log = logging.getLogger(__name__)


def convert_git_ssh_url_to_https(url: str) -> str:
    """Convert a Git SSH URI to HTTPS."""
    return re.sub(
        r'\.git$', '',
        re.sub(r'\.([a-z]+):',
               r'.\1/',
               re.sub(r'^(?:[a-z0-9A-Z]+@)?', 'https://', url, count=1),
               count=1))


def get_github_default_branch(*,
                              repo: Repo,
                              token: str,
                              base_url: str | None = None,
                              origin_name: str = 'origin') -> str:
    import github  # noqa: PLC0415
    return github.Github(token, base_url=base_url or github.Consts.DEFAULT_BASE_URL).get_repo(
        urlparse(convert_git_ssh_url_to_https(
            repo.remote(origin_name).url)).path[1:]).default_branch


def merge_dependabot_pull_requests(
    *,
    token: str,
    affiliation: str = 'owner',
    base_url: str | None = None,
) -> None:
    """Merge pull requests made by Dependabot on GitHub."""
    import github  # noqa: PLC0415

    def uses_dependabot(repo: Repository) -> bool:
        try:
            if repo.security_and_analysis.dependabot_security_updates.status == 'enabled':
                return True
        except (AttributeError, github.GithubException):
            pass
        try:
            repo.get_contents('.github/workflows/dependabot.yml')
        except github.GithubException:
            return False
        else:
            return True

    should_raise = False
    for repo in (
            x for x in github.Github(
                token, base_url=base_url or github.Consts.DEFAULT_BASE_URL, per_page=100).get_user(
                ).get_repos(affiliation=affiliation, sort='full_name')  # type: ignore[call-arg]
            if not x.archived and uses_dependabot(x)):
        log.info('Repository: %s', repo.name)
        for num in (x.number for x in repo.get_pulls() if x.user.login == 'dependabot[bot]'):
            try:
                pull = repo.get_pull(num)
                if not pull.merge(merge_method='rebase').merged:
                    pull.as_issue().create_comment('@dependabot rebase')
            except github.GithubException:
                should_raise = True
    if should_raise:
        raise RuntimeError