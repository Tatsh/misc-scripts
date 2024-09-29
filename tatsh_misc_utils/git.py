from urllib.parse import urlparse
import re

from git import Repo
import github

__all__ = ('convert_git_ssh_url_to_https', 'get_github_default_branch')


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
                              base_url: str = github.Consts.DEFAULT_BASE_URL,
                              origin_name: str = 'origin') -> str:
    return github.Github(token, base_url=base_url).get_repo(
        urlparse(convert_git_ssh_url_to_https(
            repo.remote(origin_name).url)).path[1:]).default_branch
