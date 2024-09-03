#!/usr/bin/env python
from datetime import UTC, datetime
from typing import Final, Literal, TypedDict, cast

import click
import requests

from .utils import strip_ansi_if_no_colors

__all__ = ('SalaryResponse', 'calculate_salary')

# Find the API key by looking at requests on this page
# http://www.symmetry.com/try-it-for-free/calculators
API_KEY: Final[str] = 'RnFqNFA0NVlRTExEenRwWjNiRnJrTXY4WkZHZEpkcENEeFFzQ3F0Nnh5VT0='
POST_URI: Final[str] = ('https://calculators.symmetry.com/api/calculators/'
                        'hourly?report=none')
REFERER: Final[str] = 'https://www.symmetry.com/'

INCITS38Code = Literal['AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'FM', 'GA',
                       'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH',
                       'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV',
                       'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'PW', 'RI', 'SC', 'SD', 'TN', 'TX', 'UM',
                       'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WV', 'WY']


class ContentDict(TypedDict):
    federal: float
    fica: float
    medicare: float
    netPay: float
    state: INCITS38Code


class ResponseDict(TypedDict):
    content: ContentDict


class SalaryResponse:
    def __init__(self, *, federal: float, fica: float, gross: float, medicare: float,
                 net_pay: float, state: float) -> None:
        self.federal = federal
        self.fica = fica
        self.fuckery = gross - net_pay
        self.gross = gross
        self.medicare = medicare
        self.net_pay = net_pay
        self.state = state

    def __str__(self) -> str:
        return strip_ansi_if_no_colors(f"""Gross     \033[1;32m{self.gross:8.2f}\033[0m
Federal   \033[1;32m{self.federal:8.2f}\033[0m
FICA      \033[1;32m{self.fica:8.2f}\033[0m
Medicare  \033[1;32m{self.medicare:8.2f}\033[0m
State     \033[1;32m{self.state:8.2f}\033[0m
------------------
Net       \033[1;32m{self.net_pay:8.2f}\033[0m

------------------
Fuckery   \033[1;31m{self.fuckery:8.2f}\033[0m""")


def calculate_salary(*,
                     hours: int = 70,
                     pay_rate: float = 70.0,
                     state: INCITS38Code = 'FL') -> SalaryResponse:
    check_date = int(datetime.now(tz=UTC).timestamp() * 1000)
    gross_pay = hours * pay_rate
    req = requests.post(POST_URI,
                        headers={
                            'accept': 'application/json, text/javascript, */*; q=0.01',
                            'cache-control': 'no-cache',
                            'dnt': '1',
                            'origin': 'https://www.symmetry.com',
                            'pcc-api-key': API_KEY,
                            'referer': REFERER
                        },
                        json={
                            'checkDate': check_date,
                            'state': state.upper(),
                            'rates': [{
                                'payRate': str(pay_rate),
                                'hours': str(hours),
                            }],
                            'grossPay': str(gross_pay),
                            'grossPayType': 'PAY_PER_PERIOD',
                            'grossPayYTD': '0',
                            'payFrequency': 'MONTHLY',
                            'exemptFederal': 'false',
                            'exemptFica': 'false',
                            'exemptMedicare': 'false',
                            'federalFilingStatusType': 'SINGLE',
                            'federalAllowances': '0',
                            'additionalFederalWithholding': '0',
                            'roundFederalWithholding': 'false',
                            'print': {
                                'checkDate': check_date,
                                'checkNumber': '',
                                'checkNumberOnCheck': 'false',
                                'companyAddressLine1': '',
                                'companyAddressLine2': '',
                                'companyAddressLine3': '',
                                'companyName': '',
                                'companyNameOnCheck': 'false',
                                'employeeAddressLine1': '',
                                'employeeAddressLine2': '',
                                'employeeAddressLine3': '',
                                'employeeName': '',
                                'id': '',
                                'remarks': ''
                            },
                            'otherIncome': [],
                            'payCodes': [],
                            'stockOptions': [],
                            'stateInfo': {
                                'parms': [{
                                    'name': 'TOTALALLOWANCES',
                                    'value': '0'
                                }, {
                                    'name': 'additionalStateWithholding',
                                    'value': '0'
                                }, {
                                    'name': 'SPOUSEBLINDNESS',
                                    'value': 'false'
                                }, {
                                    'name': 'stateExemption',
                                    'value': 'false'
                                }, {
                                    'name': 'PERSONALBLINDNESS',
                                    'value': 'false'
                                }, {
                                    'name': 'HEADOFHOUSEHOLD',
                                    'value': 'false'
                                }, {
                                    'name': 'FULLTIMESTUDENT',
                                    'value': 'false'
                                }]
                            },
                            'voluntaryDeductions': [],
                            'presetDeductions': []
                        },
                        timeout=30)
    req.raise_for_status()
    data = cast(ResponseDict, req.json())['content']
    return SalaryResponse(federal=data['federal'],
                          fica=data['fica'],
                          gross=gross_pay,
                          medicare=data['medicare'],
                          net_pay=data['netPay'],
                          state=data['state'])


@click.command()
@click.option('-H', '--hours', default=160, help='Hours worked in a month.')
@click.option('-r', '--pay-rate', default=70.0, help='Dollars per hour.')
@click.option('-s',
              '--state',
              default='FL',
              type=click.Choice(INCITS38Code.__args__),
              help='US state abbreviation.')
def main(hours: int = 160, pay_rate: float = 70.0, state: INCITS38Code = 'FL') -> None:
    click.echo(str(calculate_salary(hours=hours, pay_rate=pay_rate, state=state)))
