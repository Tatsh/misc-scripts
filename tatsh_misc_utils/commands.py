from collections.abc import Sequence

import click

from tatsh_misc_utils import where_from

from .adp import calculate_salary
from .utils import INCITS38Code, add_cdda_times, wait_for_disc


@click.command()
@click.argument('drive_path', type=click.Path(exists=True, dir_okay=False, writable=True))
@click.option('-w', '--wait-time', type=float, default=1.0)
def wait_for_disc_main(drive_path: str, wait_time: float = 1.0) -> None:
    if not wait_for_disc(drive_path, wait_time=wait_time):
        raise click.Abort


@click.command()
@click.option('-H', '--hours', default=160, help='Hours worked in a month.')
@click.option('-r', '--pay-rate', default=70.0, help='Dollars per hour.')
@click.option('-s',
              '--state',
              default='FL',
              type=click.Choice(INCITS38Code.__args__),
              help='US state abbreviation.')
def adp_main(hours: int = 160, pay_rate: float = 70.0, state: INCITS38Code = 'FL') -> None:
    click.echo(str(calculate_salary(hours=hours, pay_rate=pay_rate, state=state)))


@click.command()
@click.argument('times', nargs=-1)
def add_cdda_times_main(times: tuple[str, ...]) -> None:
    if (result := add_cdda_times(times)) is None:
        raise click.Abort
    click.echo(result)


@click.command('Determine where downloaded files came from.')
@click.argument('files',
                metavar='FILE',
                nargs=-1,
                type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('-w', '--webpage', is_flag=True, help='Print the webpage URL (macOS only).')
def where_from_main(files: Sequence[str], *, webpage: bool = False) -> None:
    has_multiple = len(files) > 1
    for arg in files:
        if has_multiple:
            click.echo(f'{arg}: ', nl=False)
        click.echo(where_from(arg, webpage=webpage))
