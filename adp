#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from datetime import datetime
from typing import TypedDict, cast
import argparse
import sys

from typing_extensions import Final
import requests

try:
    import argcomplete
except ImportError:
    argcomplete = None

# Find the API key by looking at requests on this page
# http://www.symmetry.com/try-it-for-free/calculators
API_KEY: Final[str] = 'RnFqNFA0NVlRTExJUkpabmc4RHErUT09'
POST_URI: Final[str] = ('https://calculators.symmetry.com/api/calculators/'
                        'hourly?report=none')
REFERER: Final[str] = (
    'https://www.adp.com/tools-and-resources/calculators-and-tools/'
    'payroll-calculators/hourly-paycheck-calculator.aspx')


class ContentDict(TypedDict):
    federal: float
    fica: float
    state: float
    medicare: float
    netPay: float


class ResponseDict(TypedDict):
    content: ContentDict


class Namespace(argparse.Namespace):
    hours: int
    pay_rate: float
    state: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description=('This is a very basic '
                     'interface to the page here: '
                     'http://www.symmetry.com/try-it-for-free/calculators'))
    parser.add_argument('-s',
                        '--state',
                        default='FL',
                        help='US state abbreviation.')
    parser.add_argument('-r',
                        '--pay-rate',
                        default=70,
                        type=float,
                        help='Pay rate in USD as a plain float.')
    parser.add_argument('-H',
                        '--hours',
                        type=int,
                        help='Hours worked in a month.',
                        default=160)
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = cast(Namespace, parser.parse_args())
    check_date = int(datetime.now().timestamp() * 1000)
    gross_pay = args.hours * args.pay_rate
    r = requests.post(POST_URI,
                      headers={
                          'pcc-api-key': API_KEY,
                          'referer': REFERER,
                          'origin': 'https://www.adp.com',
                      },
                      json={
                          'checkDate':
                          check_date,
                          'state':
                          args.state.upper(),
                          'rates': [{
                              'payRate': str(args.pay_rate),
                              'hours': str(args.hours),
                          }],
                          'grossPay':
                          str(gross_pay),
                          'grossPayType':
                          'PAY_PER_PERIOD',
                          'grossPayYTD':
                          '0',
                          'payFrequency':
                          'MONTHLY',
                          'exemptFederal':
                          'false',
                          'exemptFica':
                          'false',
                          'exemptMedicare':
                          'false',
                          'federalFilingStatusType':
                          'SINGLE',
                          'federalAllowances':
                          '0',
                          'additionalFederalWithholding':
                          '0',
                          'roundFederalWithholding':
                          'false',
                          'print': {
                              'id': '',
                              'employeeName': '',
                              'employeeAddressLine1': '',
                              'employeeAddressLine2': '',
                              'employeeAddressLine3': '',
                              'checkNumber': '',
                              'checkNumberOnCheck': 'false',
                              'checkDate': check_date,
                              'remarks': '',
                              'companyNameOnCheck': 'false',
                              'companyName': '',
                              'companyAddressLine1': '',
                              'companyAddressLine2': '',
                              'companyAddressLine3': ''
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
                      })
    r.raise_for_status()
    data = cast(ResponseDict, r.json())['content']
    print('Gross     \033[1;32m{:8.2f}\033[0m'.format(gross_pay))
    print('Federal   \033[1;32m{:8.2f}\033[0m'.format(data['federal']))
    print('FICA      \033[1;32m{:8.2f}\033[0m'.format(data['fica']))
    print('State     \033[1;32m{:8.2f}\033[0m'.format(data['state']))
    print('Medicare  \033[1;32m{:8.2f}\033[0m'.format(data['medicare']))
    print('------------------')
    print('Net       \033[1;32m{:8.2f}\033[0m'.format(data['netPay']))
    print('')
    print('------------------')
    print('Fuckery   \033[1;31m{:8.2f}\033[0m'.format(gross_pay -
                                                      data['netPay']))

    return 0


if __name__ == '__main__':
    sys.exit(main())
